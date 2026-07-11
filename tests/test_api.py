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
