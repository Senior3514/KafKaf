"""OllamaBrain.generate_stream against a mocked transport (httpx's own
httpx.MockTransport, no new dependency) -- proves the NDJSON parsing and
chunk-yielding logic without needing a real Ollama server. Also covers
Brain's default generate_stream fallback for brains that don't override it."""

import httpx
import pytest

from kafkaf.core.brains.base import Brain
from kafkaf.core.brains.ollama_brain import OllamaBrain


def _ndjson_response(lines: list[str]) -> httpx.Response:
    body = "\n".join(lines) + "\n"
    return httpx.Response(200, content=body.encode(), headers={"content-type": "application/x-ndjson"})


@pytest.mark.asyncio
async def test_ollama_generate_stream_yields_chunks_in_order(monkeypatch):
    lines = [
        '{"message": {"content": "Hel"}, "done": false}',
        '{"message": {"content": "lo"}, "done": false}',
        '{"done": true}',
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return _ndjson_response(lines)

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.AsyncClient

    def patched_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr("kafkaf.core.brains.ollama_brain.httpx.AsyncClient", patched_client)

    brain = OllamaBrain(model="test-model", host="http://fake-ollama")
    chunks = [chunk async for chunk in brain.generate_stream([{"role": "user", "content": "hi"}])]
    assert chunks == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_ollama_generate_stream_raises_on_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"internal error")

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.AsyncClient

    def patched_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr("kafkaf.core.brains.ollama_brain.httpx.AsyncClient", patched_client)

    brain = OllamaBrain(model="test-model", host="http://fake-ollama")
    with pytest.raises(httpx.HTTPStatusError):
        async for _ in brain.generate_stream([{"role": "user", "content": "hi"}]):
            pass


@pytest.mark.asyncio
async def test_default_generate_stream_yields_whole_reply_once():
    class PlainBrain(Brain):
        name = "plain"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            return "a complete reply"

    brain = PlainBrain()
    chunks = [chunk async for chunk in brain.generate_stream([{"role": "user", "content": "hi"}])]
    assert chunks == ["a complete reply"]
