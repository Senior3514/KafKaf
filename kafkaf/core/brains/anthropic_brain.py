import httpx

from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings


class AnthropicBrain(Brain):
    """Talks to the Anthropic Messages API. Requires KAFKAF_ANTHROPIC_API_KEY."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.name = model or settings.anthropic_model
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise RuntimeError("KAFKAF_ANTHROPIC_API_KEY is not set.")

    async def generate(self, messages: list[dict[str, str]]) -> str:
        messages = list(messages)
        system_prompt = None
        if messages and messages[0]["role"] == "system":
            system_prompt = messages.pop(0)["content"]

        payload: dict = {"model": self.name, "max_tokens": 1024, "messages": messages}
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"]
