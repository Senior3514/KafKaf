import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kafkaf.core import autonomy, council
from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.registry import get_brain
from kafkaf.core.config import settings
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


class ChatResponse(BaseModel):
    reply: str
    session_id: str


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
        reply = await council.handle_chat(
            request.session_id,
            request.message,
            request.persona,
            brain=brain,
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

    return ChatResponse(reply=reply, session_id=request.session_id)


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
        "council": {
            "configured": bool(council_brains),
            "brains": council_brains,
        },
        "own_model": enrichment_service.get_status(),
        "default_teacher": f"ollama:{settings.ollama_model}",
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
