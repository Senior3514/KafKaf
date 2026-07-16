import httpx

from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings

# Separate connect vs. read timeouts: if Ollama genuinely isn't reachable
# (not running, wrong host/port, blocked by a VM's network layer), that
# should fail fast — not hang for two full minutes looking exactly like a
# frozen app before finally erroring. A real, slow model generating a long
# reply still gets the full 120s once a connection is actually established.
_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)


class OllamaBrain(Brain):
    """Talks to a local Ollama server — the default, private, free brain."""

    def __init__(self, model: str | None = None, host: str | None = None):
        self.name = model or settings.ollama_model
        self.host = host or settings.ollama_host

    async def generate(self, messages: list[dict[str, str]]) -> str:
        async with httpx.AsyncClient(base_url=self.host, timeout=_TIMEOUT) as client:
            response = await client.post(
                "/api/chat",
                json={"model": self.name, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
