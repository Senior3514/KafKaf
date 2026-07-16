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
from kafkaf.core.memory import store
from kafkaf.core.rate_limit import RateLimitMiddleware
from kafkaf.core.skills import store as skills_store

WEB_DIR = Path(__file__).resolve().parent.parent / "clients" / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    skills_store.init_db()
    audit_store.init_db()
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
        raise HTTPException(
            status_code=502,
            detail=f"Couldn't get a reply from the model ({exc}). Is Ollama running "
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
