import pytest
from fastapi.testclient import TestClient

from kafkaf.core import council
from kafkaf.core.api import app
from kafkaf.core.brains.base import Brain

# `app` is a module-level singleton and Starlette caches its middleware
# stack (including RateLimitMiddleware's per-key hit counters) after the
# first request, so every test here uses its own fake client IP — sharing
# one would leak rate-limit state across tests.


class FakeBrain(Brain):
    name = "fake"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return "pong"


@pytest.fixture(autouse=True)
def _use_fake_brain(monkeypatch, tmp_path):
    monkeypatch.setattr(council, "_default_brain", FakeBrain())
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    yield


def test_requests_within_limit_pass(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.rate_limit_per_minute", 2)
    with TestClient(app, client=("10.11.0.1", 1)) as client:
        r1 = client.post("/chat", json={"message": "hi", "session_id": "a"})
        r2 = client.post("/chat", json={"message": "hi", "session_id": "a"})
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_requests_over_limit_get_429(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.rate_limit_per_minute", 2)
    with TestClient(app, client=("10.11.0.2", 1)) as client:
        client.post("/chat", json={"message": "hi", "session_id": "b"})
        client.post("/chat", json={"message": "hi", "session_id": "b"})
        third = client.post("/chat", json={"message": "hi", "session_id": "b"})
    assert third.status_code == 429
    assert "detail" in third.json()


def test_limit_zero_disables_rate_limiting(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.rate_limit_per_minute", 0)
    with TestClient(app, client=("10.11.0.3", 1)) as client:
        responses = [
            client.post("/chat", json={"message": "hi", "session_id": "c"}) for _ in range(10)
        ]
    assert all(r.status_code == 200 for r in responses)


def test_health_and_static_are_exempt(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.rate_limit_per_minute", 1)
    with TestClient(app, client=("10.11.0.4", 1)) as client:
        for _ in range(5):
            assert client.get("/health").status_code == 200
            assert client.get("/static/app.js").status_code == 200
