import pytest
from fastapi.testclient import TestClient

from kafkaf.core import council
from kafkaf.core.api import app
from kafkaf.core.brains.base import Brain


class FakeBrain(Brain):
    name = "fake"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return "pong"


@pytest.fixture(autouse=True)
def _use_fake_brain(monkeypatch, tmp_path):
    monkeypatch.setattr(council, "_default_brain", FakeBrain())
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    yield


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat():
    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"message": "ping", "session_id": "test-session"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "pong"
    assert body["session_id"] == "test-session"


def test_chat_remembers_history():
    with TestClient(app) as client:
        client.post("/chat", json={"message": "first", "session_id": "s1"})
        client.post("/chat", json={"message": "second", "session_id": "s1"})

    history = council.store.get_history("s1")
    assert [m["content"] for m in history] == ["first", "pong", "second", "pong"]


def test_web_gui_served_at_root():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "KafKaf" in response.text


def test_web_gui_static_assets():
    with TestClient(app) as client:
        js = client.get("/static/app.js")
        css = client.get("/static/style.css")
    assert js.status_code == 200
    assert css.status_code == 200


def test_chat_brain_override_used(monkeypatch):
    class OverrideBrain(Brain):
        name = "override"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            return "override-pong"

    monkeypatch.setattr("kafkaf.core.api.get_brain", lambda spec: OverrideBrain())

    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"message": "hi", "session_id": "s2", "brain": "ollama:llama3"}
        )
    assert response.status_code == 200
    assert response.json()["reply"] == "override-pong"


def test_chat_invalid_brain_spec_returns_400():
    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"message": "hi", "session_id": "s3", "brain": "no-colon-here"}
        )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_chat_unknown_provider_returns_400():
    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"message": "hi", "session_id": "s4", "brain": "bogus:model"}
        )
    assert response.status_code == 400


def test_chat_council_without_config_returns_400():
    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "hi", "session_id": "s5", "council": True})
    assert response.status_code == 400


def test_chat_council_mode_uses_configured_brains(monkeypatch):
    class BrainA(Brain):
        name = "brain-a"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            return "answer A"

    class BrainB(Brain):
        name = "brain-b"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            return "answer B"

    brains = {"ollama:a": BrainA(), "ollama:b": BrainB()}
    monkeypatch.setattr("kafkaf.core.config.settings.council_brains", "ollama:a,ollama:b")
    monkeypatch.setattr("kafkaf.core.council.get_brain", lambda spec: brains[spec])

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "hi", "session_id": "s6", "council": True})
    assert response.status_code == 200
    # synthesized by the fixture's default brain (FakeBrain -> always "pong")
    assert response.json()["reply"] == "pong"


def test_audit_endpoint_returns_recent_events():
    with TestClient(app) as client:
        client.post("/chat", json={"message": "ping", "session_id": "audit-test"})
        response = client.get("/audit")
    assert response.status_code == 200
    events = response.json()
    assert any(e["event_type"] == "chat" and e["actor"] == "fake" for e in events)


def test_audit_endpoint_filters_by_event_type():
    with TestClient(app) as client:
        client.post("/chat", json={"message": "ping", "session_id": "audit-test-2"})
        response = client.get("/audit", params={"event_type": "chat_skills"})
    assert response.status_code == 200
    assert response.json() == []


def test_chat_skills_mode_executes_tools(monkeypatch):
    class ScriptedBrain(Brain):
        name = "scripted"

        def __init__(self):
            self.calls = 0

        async def generate(self, messages: list[dict[str, str]]) -> str:
            self.calls += 1
            if self.calls == 1:
                return "ACTION: calculator: 6 * 7"
            return "FINAL ANSWER: the answer is 42"

    monkeypatch.setattr(council, "_default_brain", ScriptedBrain())

    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"message": "what is 6*7?", "session_id": "s7", "skills": True}
        )
    assert response.status_code == 200
    assert response.json()["reply"] == "the answer is 42"
