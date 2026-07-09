from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from kafkaf.core import council
from kafkaf.core.memory import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    yield


app = FastAPI(title="KafKaf", version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    persona: str = "default"


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = await council.handle_chat(
        request.session_id, request.message, request.persona
    )
    return ChatResponse(reply=reply, session_id=request.session_id)
