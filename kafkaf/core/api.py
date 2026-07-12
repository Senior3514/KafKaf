from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kafkaf.core import council
from kafkaf.core.brains.registry import get_brain
from kafkaf.core.memory import store

WEB_DIR = Path(__file__).resolve().parent.parent / "clients" / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    yield


app = FastAPI(title="KafKaf", version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    persona: str = "default"
    # Optional teacher/brain override, e.g. "own" or "ollama:llama3" — lets a
    # client (like the web GUI's model toggle) talk to a specific brain
    # instead of the default one, reusing the same registry MCP tools use.
    brain: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    brain = None
    if request.brain:
        try:
            brain = get_brain(request.brain)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        reply = await council.handle_chat(
            request.session_id, request.message, request.persona, brain=brain
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatResponse(reply=reply, session_id=request.session_id)


@app.get("/", include_in_schema=False)
async def web_index() -> FileResponse:
    """The mobile-first web GUI, served directly by the backend — no separate
    build step or Node toolchain required."""
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
