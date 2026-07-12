import httpx

from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings


class OllamaBrain(Brain):
    """Talks to a local Ollama server — the default, private, free brain."""

    def __init__(self, model: str | None = None, host: str | None = None):
        self.name = model or settings.ollama_model
        self.host = host or settings.ollama_host

    async def generate(self, messages: list[dict[str, str]]) -> str:
        async with httpx.AsyncClient(base_url=self.host, timeout=120.0) as client:
            response = await client.post(
                "/api/chat",
                json={"model": self.name, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
