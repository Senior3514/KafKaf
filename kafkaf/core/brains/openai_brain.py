import httpx

from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings


class OpenAIBrain(Brain):
    """Talks to the OpenAI Chat Completions API. Requires KAFKAF_OPENAI_API_KEY."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.name = model or settings.openai_model
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise RuntimeError("KAFKAF_OPENAI_API_KEY is not set.")

    async def generate(self, messages: list[dict[str, str]]) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.name, "messages": messages},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
