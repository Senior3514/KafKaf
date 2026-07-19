import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kafkaf.core import autonomy, council
from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.registry import get_brain
from kafkaf.core.config import settings
from kafkaf.core.enrichment.autopilot import _default_stop_file, is_stop_requested
from kafkaf.core.enrichment import service as enrichment_service
from kafkaf.core.enrichment import store as enrichment_store
from kafkaf.core.memory import store
from kafkaf.core.rate_limit import RateLimitMiddleware
from kafkaf.core.skills import store as skills_store

WEB_DIR = Path(__file__).resolve().parent.parent / "clients" / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    skills_store.init_db()
    audit_store.init_db()
    enrichment_store.init_db()
    yield


app = FastAPI(title="KafKaf", version="0.1.0", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort backstop, not a substitute for specific error handling.
    Every response from this API must be JSON, success or failure — the
    web GUI's client always does response.json() and shows a clean error
    bubble, never a raw framework error page. Route handlers should keep
    catching what they can identify to give a useful, specific message
    (see /chat's brain-resolution and council-call except clauses); this
    exists because that same "narrow except clause misses a case" bug
    class has shipped three times as one-off fixes for three different
    code paths (docs/ROADMAP.md phases 15/18/19) — this is the structural
    fix so a fourth still-unknown code path can't repeat it. Registering a
    handler for the base Exception overrides Starlette's outermost
    ServerErrorMiddleware, so this also catches exceptions raised in
    middleware (e.g. RateLimitMiddleware), not just inside route bodies."""
    reason = str(exc) or type(exc).__name__
    return JSONResponse(status_code=500, content={"detail": f"Unexpected server error: {reason}"})


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    persona: str = "default"
    # Optional teacher/brain override, e.g. "own" or "ollama:llama3" — lets a
    # client (like the web GUI's model toggle) talk to a specific brain
    # instead of the default one, reusing the same registry MCP tools use.
    brain: str | None = None
    # Fan the query out to every brain in KAFKAF_COUNCIL_BRAINS and
    # synthesize one answer, instead of a single brain replying directly.
    council: bool = False
    # Let the brain(s) use tools (web search, calculator, files, reminders,
    # ...) via the ReAct loop. Combines with council=true — each council
    # brain runs the tool-use loop independently before answers are
    # synthesized — see kafkaf/core/council.py.
    skills: bool = False


class PendingApprovalOut(BaseModel):
    approval_id: int
    skill_name: str
    skill_arg: str


class ChatResponse(BaseModel):
    reply: str | None = None
    session_id: str
    # Set instead of reply when a requested skill (run_code,
    # browser_automate) needs a live human approve/deny click before it
    # can run — see /skills/approvals/{id}/approve|deny, which return this
    # exact same response shape so the frontend has one rendering path.
    pending_approval: PendingApprovalOut | None = None


class TeachRequest(BaseModel):
    topic: str
    fact: str


class DistillRequest(BaseModel):
    topic: str
    teacher: str
    instruction: str = ""


class TrainRequest(BaseModel):
    steps: int = 50


class AutonomyRequest(BaseModel):
    level: str


class WriteSkillsModeRequest(BaseModel):
    mode: str


class WorkspaceRequest(BaseModel):
    path: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if request.skills and not autonomy.skills_allowed():
        raise HTTPException(
            status_code=400,
            detail=f"skills are disabled at autonomy level {settings.autonomy_level!r} "
            "(needs 'assisted' or 'autonomous' — see docs/SETUP.md#autonomy-levels).",
        )

    brain = None
    if request.brain:
        try:
            brain = get_brain(request.brain)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ModuleNotFoundError as exc:
            # get_brain("own") lazily imports OwnModelBrain, which imports
            # torch — an optional [train] extra. On a machine that only
            # installed the base package (the common case), that import
            # fails here, before the broad except-Exception fallback below
            # is even reached — this must not fall through to a raw,
            # non-JSON 500 (found live: selecting "Our own model" in the
            # web GUI without [train] installed did exactly that).
            raise HTTPException(
                status_code=400,
                detail=f"Can't use brain {request.brain!r}: {exc}. If this is "
                '"own", it needs the optional \'train\' extra: run '
                'pip install -e ".[train]" (installs torch), then restart the server.',
            ) from exc

    council_brains = None
    if request.council:
        council_brains = [s.strip() for s in (settings.council_brains or "").split(",") if s.strip()]
        if not council_brains:
            raise HTTPException(
                status_code=400,
                detail="Council mode requested but KAFKAF_COUNCIL_BRAINS is not configured.",
            )

    try:
        outcome = await council.handle_chat(
            request.session_id,
            request.message,
            request.persona,
            brain=brain,
            brain_spec=request.brain,
            council_brains=council_brains,
            use_skills=request.skills,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # A brain call failing (Ollama unreachable, model not pulled, a
        # network error, ...) must not surface as a raw framework 500 page —
        # the web GUI expects JSON back from every response, success or
        # failure, and an HTML error page fails client-side JSON parsing
        # with a confusing "Unexpected token" instead of the real problem.
        # Some exceptions (httpx's timeout classes in particular) stringify
        # to "" with no message at all — fall back to the exception's type
        # name so the detail is never a useless empty "()".
        reason = str(exc) or type(exc).__name__
        raise HTTPException(
            status_code=502,
            detail=f"Couldn't get a reply from the model ({reason}). Is Ollama running "
            "and is the model pulled? See docs/USAGE.md#common-day-to-day-commands.",
        ) from exc

    return _chat_response(outcome)


def _chat_response(outcome: council.ChatOutcome) -> ChatResponse:
    pending = (
        PendingApprovalOut(**outcome.pending_approval) if outcome.pending_approval else None
    )
    return ChatResponse(reply=outcome.reply, session_id=outcome.session_id, pending_approval=pending)


async def _decide_approval(approval_id: int, decision: str) -> ChatResponse:
    try:
        outcome = await council.resume_chat(approval_id, decision)
    except council.ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except council.ApprovalAlreadyDecidedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        reason = str(exc) or type(exc).__name__
        raise HTTPException(status_code=502, detail=f"Couldn't resume the conversation ({reason}).") from exc
    return _chat_response(outcome)


@app.post("/skills/approvals/{approval_id}/approve", response_model=ChatResponse)
async def approve_skill_action(approval_id: int) -> ChatResponse:
    return await _decide_approval(approval_id, "approved")


@app.post("/skills/approvals/{approval_id}/deny", response_model=ChatResponse)
async def deny_skill_action(approval_id: int) -> ChatResponse:
    return await _decide_approval(approval_id, "denied")


@app.get("/skills/approvals")
async def list_pending_approvals(status: str = "pending") -> list[dict]:
    return skills_store.list_approvals(status=status)


@app.get("/audit")
async def audit(limit: int = 50, event_type: str | None = None) -> list[dict]:
    return audit_store.recent_events(limit=limit, event_type=event_type)


@app.get("/autonomy")
async def autonomy_status() -> dict:
    return {
        "level": settings.autonomy_level,
        "description": autonomy.DESCRIPTIONS[settings.autonomy_level],
        "skills_allowed": autonomy.skills_allowed(),
    }


@app.post("/autonomy")
async def set_autonomy(request: AutonomyRequest) -> dict:
    """Change the autonomy level for this running process immediately — no
    restart needed for /chat's skills gate to reflect it. Honest about
    scope: this affects *this* process only. A separately-running autopilot
    container (Docker) reads its own environment at startup and is not
    touched by this; persisting the choice across a restart of this process
    still needs KAFKAF_AUTONOMY_LEVEL set in the environment/.env file."""
    if request.level not in autonomy.TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown autonomy level {request.level!r}. Must be one of {autonomy.TIERS}.",
        )
    settings.autonomy_level = request.level
    return {
        "level": settings.autonomy_level,
        "description": autonomy.DESCRIPTIONS[settings.autonomy_level],
        "skills_allowed": autonomy.skills_allowed(),
    }


@app.get("/skills/write-mode")
async def write_skills_mode_status() -> dict:
    return {
        "mode": settings.write_skills_mode,
        "description": autonomy.WRITE_SKILLS_DESCRIPTIONS[settings.write_skills_mode],
    }


@app.post("/skills/write-mode")
async def set_write_skills_mode(request: WriteSkillsModeRequest) -> dict:
    """A second, independent dial from /autonomy — see
    Settings.write_skills_mode. Live for this process immediately, same
    scope caveats as /autonomy (doesn't reach a separate autopilot
    container, doesn't persist without KAFKAF_WRITE_SKILLS_MODE also set)."""
    if request.mode not in autonomy.WRITE_SKILLS_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown write-skills mode {request.mode!r}. Must be one of {autonomy.WRITE_SKILLS_MODES}.",
        )
    settings.write_skills_mode = request.mode
    return {
        "mode": settings.write_skills_mode,
        "description": autonomy.WRITE_SKILLS_DESCRIPTIONS[settings.write_skills_mode],
    }


@app.get("/autopilot/status")
async def autopilot_status() -> dict:
    """Whether an emergency stop is currently in effect for autopilot.
    Uses the same stop-file the loop itself checks (AUTOPILOT_STOP_FILE
    when set — e.g. /data/autopilot.stop in Docker, where the backend
    shares the /data volume with the autopilot container)."""
    stop_file = _default_stop_file()
    return {"stopped": is_stop_requested(stop_file), "stop_file": stop_file}


@app.post("/autopilot/stop")
async def autopilot_stop() -> dict:
    """Emergency stop from the GUI — same mechanism as
    `kafkaf-autopilot-ctl stop`, no terminal needed. A running autopilot
    halts within a few seconds; the stop persists until resumed."""
    stop_file = _default_stop_file()
    try:
        Path(stop_file).touch()
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Couldn't write stop file {stop_file!r}: {exc}"
        ) from exc
    audit_store.log_event("autopilot_stop", "web", f"emergency stop requested via GUI ({stop_file!r})")
    return {"stopped": True, "stop_file": stop_file}


@app.post("/autopilot/resume")
async def autopilot_resume() -> dict:
    """Clear the emergency stop so autopilot can run again."""
    stop_file = _default_stop_file()
    try:
        Path(stop_file).unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Couldn't remove stop file {stop_file!r}: {exc}"
        ) from exc
    audit_store.log_event("autopilot_resume", "web", f"stop cleared via GUI ({stop_file!r})")
    return {"stopped": False, "stop_file": stop_file}


@app.post("/skills/workspace")
async def set_skills_workspace(request: WorkspaceRequest) -> dict:
    """Point the filesystem-touching skills (files, document_search,
    journal) at a real directory the user explicitly chooses — the same
    "you pick one working directory" model as Claude Code's own cwd, not
    unrestricted access to the whole machine. Whatever directory is set
    here becomes the sandbox root: kafkaf/core/skills/sandbox.py still
    rejects any path that tries to escape it (../, absolute paths outside
    it) — the boundary just moves to wherever this points, deliberately
    and visibly, instead of being fixed to the app-local ./workspace."""
    try:
        resolved = Path(request.path).expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=400, detail=f"Can't use {request.path!r} as a workspace: {exc}"
        ) from exc

    settings.skills_workspace_dir = str(resolved)
    return {"skills_workspace_dir": settings.skills_workspace_dir}


@app.get("/status")
async def status() -> dict:
    """Everything a Control Panel needs in one call: autonomy level, own-model
    training progress, and what skills/autopilot are actually allowed to do —
    the "full control and configuration" view, in one place, instead of
    scattered across docs and CLI commands."""
    council_brains = [s.strip() for s in (settings.council_brains or "").split(",") if s.strip()]
    return {
        "autonomy": {
            "level": settings.autonomy_level,
            "description": autonomy.DESCRIPTIONS[settings.autonomy_level],
            "skills_allowed": autonomy.skills_allowed(),
        },
        "write_skills_mode": {
            "mode": settings.write_skills_mode,
            "description": autonomy.WRITE_SKILLS_DESCRIPTIONS[settings.write_skills_mode],
        },
        "council": {
            "configured": bool(council_brains),
            "brains": council_brains,
        },
        "own_model": enrichment_service.get_status(),
        "default_teacher": f"ollama:{settings.ollama_model}",
        "skills_workspace_dir": settings.skills_workspace_dir,
        "autopilot": {"stopped": is_stop_requested(_default_stop_file())},
        "pending_approvals": {"count": len(skills_store.list_approvals(status="pending"))},
    }


@app.post("/enrichment/teach")
async def enrichment_teach(request: TeachRequest) -> dict:
    """Directly teach a fact — no model call involved. The same primitive
    the MCP server's teach_fact tool uses, reachable from the app itself."""
    return enrichment_service.teach_fact(request.topic, request.fact)


@app.post("/enrichment/distill")
async def enrichment_distill(request: DistillRequest) -> dict:
    """Ask another model (a teacher) to explain a topic and store what it
    says as training data — the captured completion is returned so teaching
    stays visible, not a blind ingestion."""
    try:
        teacher = get_brain(request.teacher)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return await enrichment_service.distill_from_teacher(request.topic, teacher, request.instruction)
    except Exception as exc:
        reason = str(exc) or type(exc).__name__
        raise HTTPException(status_code=502, detail=f"Teacher call failed ({reason}).") from exc


@app.post("/enrichment/train")
async def enrichment_train(request: TrainRequest) -> dict:
    """Actually train on what's been taught so far. Runs in a worker thread —
    training is CPU-bound sync code and must not block the event loop that
    every other request (including a concurrent /chat) shares."""
    try:
        return await asyncio.to_thread(enrichment_service.run_training_step, request.steps)
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail="Training needs the optional 'train' extra: run "
            'pip install -e ".[train]" (installs torch), then restart the server.',
        ) from exc
    except Exception as exc:
        # Any other training failure (corpus too small for the configured
        # block_size, a corrupt checkpoint, ...) must still come back as a
        # JSON error the web GUI can parse — same reasoning as /chat's
        # broad handler. Caught by a real ValueError during live testing:
        # training with too little taught data raised past a narrow
        # ModuleNotFoundError-only catch straight into a raw framework 500.
        reason = str(exc) or type(exc).__name__
        raise HTTPException(status_code=400, detail=f"Training failed ({reason}).") from exc


@app.get("/", include_in_schema=False)
async def web_index() -> FileResponse:
    """The mobile-first web GUI, served directly by the backend — no separate
    build step or Node toolchain required."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    """Served from the root, not /static/sw.js — a service worker's default
    scope is its own directory, so root-scoped is required to control the
    whole app (the chat page at '/'), not just /static/* requests."""
    return FileResponse(WEB_DIR / "sw.js", media_type="application/javascript")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
