import httpx

from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings


class GeminiBrain(Brain):
    """Talks to the Google Gemini API. Requires KAFKAF_GEMINI_API_KEY."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.name = model or settings.gemini_model
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise RuntimeError("KAFKAF_GEMINI_API_KEY is not set.")

    async def generate(self, messages: list[dict[str, str]]) -> str:
        messages = list(messages)
        system_instruction = None
        if messages and messages[0]["role"] == "system":
            system_instruction = messages.pop(0)["content"]

        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]
        payload: dict = {"contents": contents}
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.name}:generateContent?key={self.api_key}"
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
