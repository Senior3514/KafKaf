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
    assert 'id="control-toggle"' in response.text


def test_web_gui_static_assets():
    with TestClient(app) as client:
        js = client.get("/static/app.js")
        css = client.get("/static/style.css")
        i18n = client.get("/static/i18n.js")
    assert js.status_code == 200
    assert css.status_code == 200
    assert i18n.status_code == 200
    assert "TRANSLATIONS" in i18n.text


def test_pwa_manifest_and_icons_served():
    with TestClient(app) as client:
        manifest = client.get("/static/manifest.json")
        icon = client.get("/static/icons/icon-192.png")
    assert manifest.status_code == 200
    assert manifest.json()["name"] == "KafKaf"
    assert icon.status_code == 200
    assert icon.headers["content-type"] == "image/png"


def test_service_worker_served_from_root_scope():
    with TestClient(app) as client:
        response = client.get("/sw.js")
    assert response.status_code == 200
    assert "install" in response.text


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


def test_chat_own_brain_without_torch_returns_clean_400_not_raw_500(monkeypatch):
    """Found live: selecting "Our own model" in the web GUI on a machine
    that only ran `pip install -e ".[dev]"` (no [train] extra, so no
    torch) raised ModuleNotFoundError while resolving the brain — before
    the broad except-Exception fallback further down is even reached.
    That fell through to FastAPI's default handler: a raw, non-JSON 500
    ("Backend returned 500 with a non-JSON body" in the web GUI), the same
    bug class already fixed twice this session elsewhere."""

    def boom(spec: str):
        raise ModuleNotFoundError("No module named 'torch'")

    monkeypatch.setattr("kafkaf.core.api.get_brain", boom)

    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"message": "hi", "session_id": "s-own-no-torch", "brain": "own"}
        )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body
    assert "train" in body["detail"]


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


def test_unhandled_exception_anywhere_still_returns_clean_json(monkeypatch):
    """The narrow-except-clause bug class (a raw, non-JSON 500 the web GUI
    can't parse) has shipped three times as one-off fixes for three
    different code paths (docs/ROADMAP.md phases 15/18/19), and was found
    live a fourth time on /chat during a mid-request package reinstall —
    a code path no specific except clause anticipated. Rather than add a
    fourth one-off patch, a global @app.exception_handler(Exception) now
    backstops every route. Proven here against a route with no try/except
    of its own at all (/audit), so this isn't just re-testing an
    already-covered path."""

    def boom(limit: int, event_type: str | None = None):
        raise RuntimeError("simulated failure with no matching except clause")

    monkeypatch.setattr("kafkaf.core.api.audit_store.recent_events", boom)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/audit")
    assert response.status_code == 500
    body = response.json()
    assert "detail" in body
    assert "simulated failure" in body["detail"]


def test_audit_endpoint_filters_by_event_type():
    with TestClient(app) as client:
        client.post("/chat", json={"message": "ping", "session_id": "audit-test-2"})
        response = client.get("/audit", params={"event_type": "chat_skills"})
    assert response.status_code == 200
    assert response.json() == []


def test_autonomy_endpoint_returns_current_level():
    with TestClient(app) as client:
        response = client.get("/autonomy")
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "autonomous"
    assert body["skills_allowed"] is True


def test_set_autonomy_changes_level_and_skills_gate(monkeypatch):
    """The Control Panel's autonomy switcher — changing level must take
    effect immediately for this process, no restart, so /chat's skills gate
    (and the web GUI's Skills checkbox) never contradicts what was picked."""
    monkeypatch.setattr("kafkaf.core.config.settings.autonomy_level", "autonomous")

    with TestClient(app) as client:
        response = client.post("/autonomy", json={"level": "observe"})
        assert response.status_code == 200
        body = response.json()
        assert body["level"] == "observe"
        assert body["skills_allowed"] is False

        # And it's really live: skills are now rejected without a restart.
        chat_response = client.post(
            "/chat", json={"message": "hi", "session_id": "s-live-autonomy", "skills": True}
        )
    assert chat_response.status_code == 400


def test_set_autonomy_rejects_unknown_level():
    with TestClient(app) as client:
        response = client.post("/autonomy", json={"level": "godmode"})
    assert response.status_code == 400
    assert "godmode" in response.json()["detail"]


def test_autopilot_stop_resume_from_the_gui(monkeypatch, tmp_path):
    """The Control Panel's Emergency Stop button — same stop-file mechanism
    as kafkaf-autopilot-ctl, no terminal needed. Also reported in /status
    so the panel renders live state in one call."""
    stop_file = str(tmp_path / "autopilot.stop")
    monkeypatch.setenv("AUTOPILOT_STOP_FILE", stop_file)

    with TestClient(app) as client:
        assert client.get("/autopilot/status").json()["stopped"] is False
        assert client.get("/status").json()["autopilot"]["stopped"] is False

        stop_response = client.post("/autopilot/stop")
        assert stop_response.status_code == 200
        assert stop_response.json()["stopped"] is True
        assert client.get("/autopilot/status").json()["stopped"] is True
        assert client.get("/status").json()["autopilot"]["stopped"] is True

        resume_response = client.post("/autopilot/resume")
        assert resume_response.status_code == 200
        assert resume_response.json()["stopped"] is False
        assert client.get("/autopilot/status").json()["stopped"] is False

        event_types = [e["event_type"] for e in client.get("/audit").json()]
    assert "autopilot_stop" in event_types
    assert "autopilot_resume" in event_types


def test_set_skills_workspace_changes_the_sandbox_root(monkeypatch, tmp_path):
    """The 'pick one directory, like Claude Code's cwd' model — this must
    move the sandbox root live, and files/document_search/journal must
    then actually operate inside the newly-chosen directory, not the old
    one."""
    new_root = tmp_path / "chosen-folder"
    with TestClient(app) as client:
        response = client.post("/skills/workspace", json={"path": str(new_root)})
    assert response.status_code == 200
    assert response.json()["skills_workspace_dir"] == str(new_root)
    assert new_root.is_dir()

    from kafkaf.core.skills.sandbox import workspace_root

    assert workspace_root() == new_root


def test_set_skills_workspace_reports_status(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.skills_workspace_dir", str(tmp_path))
    with TestClient(app) as client:
        response = client.get("/status")
    assert response.json()["skills_workspace_dir"] == str(tmp_path)


def test_status_endpoint_returns_autonomy_and_own_model_state():
    """Backs the web GUI's Control Panel — one call for "what is this
    allowed to do, and what has the own model actually learned so far"."""
    with TestClient(app) as client:
        response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["autonomy"]["level"] == "autonomous"
    assert body["council"]["configured"] is False
    assert "corpus_size" in body["own_model"]
    assert "checkpoint_exists" in body["own_model"]
    assert body["default_teacher"] == "ollama:qwen3:4b"


def test_status_endpoint_reports_council_configured(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.council_brains", "ollama:a,ollama:b")
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.json()
    assert body["council"]["configured"] is True
    assert body["council"]["brains"] == ["ollama:a", "ollama:b"]


def test_enrichment_teach_stores_a_fact_directly():
    """The web GUI's "Grow" panel — teaching a fact with no model call,
    same primitive the MCP server's teach_fact tool uses."""
    with TestClient(app) as client:
        response = client.post(
            "/enrichment/teach", json={"topic": "kafkaf", "fact": "a private AI platform"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["corpus_size"]["total"] >= 1


def test_enrichment_distill_calls_teacher_and_stores_completion(monkeypatch):
    class TeacherBrain(Brain):
        name = "teacher"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            return "Explanation of the topic."

    monkeypatch.setattr("kafkaf.core.api.get_brain", lambda spec: TeacherBrain())

    with TestClient(app) as client:
        response = client.post(
            "/enrichment/distill", json={"topic": "kafkaf", "teacher": "ollama:llama3"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["completion"] == "Explanation of the topic."
    assert body["teacher"] == "teacher"


def test_enrichment_distill_unknown_teacher_returns_400(monkeypatch):
    with TestClient(app) as client:
        response = client.post(
            "/enrichment/distill", json={"topic": "kafkaf", "teacher": "no-colon-here"}
        )
    assert response.status_code == 400


def test_enrichment_train_without_torch_installed_returns_clean_400(monkeypatch):
    """Training is an optional 'train' extra (torch) — if it isn't
    installed, the endpoint must say so clearly, not 500."""

    def boom(steps: int) -> dict:
        raise ModuleNotFoundError("No module named 'torch'")

    monkeypatch.setattr("kafkaf.core.api.enrichment_service.run_training_step", boom)

    with TestClient(app) as client:
        response = client.post("/enrichment/train", json={"steps": 10})
    assert response.status_code == 400
    assert "train" in response.json()["detail"]


def test_enrichment_train_other_failure_returns_clean_400_not_raw_500(monkeypatch):
    """Found live: training with too little taught data raises a real
    ValueError (corpus too small for block_size) from kafkaf/model/train.py.
    A narrow except-ModuleNotFoundError-only catch let that fall through to
    FastAPI's default handler — a raw, non-JSON 500 the web GUI can't
    parse, the exact bug class /chat was already fixed for."""

    def boom(steps: int) -> dict:
        raise ValueError("Corpus too small (23 bytes) for block_size=128")

    monkeypatch.setattr("kafkaf.core.api.enrichment_service.run_training_step", boom)

    with TestClient(app) as client:
        response = client.post("/enrichment/train", json={"steps": 10})
    assert response.status_code == 400
    assert "Corpus too small" in response.json()["detail"]


def test_enrichment_train_runs_and_returns_result(monkeypatch):
    monkeypatch.setattr(
        "kafkaf.core.api.enrichment_service.run_training_step",
        lambda steps: {"steps": steps, "loss_start": 2.0, "loss_end": 1.5},
    )
    with TestClient(app) as client:
        response = client.post("/enrichment/train", json={"steps": 10})
    assert response.status_code == 200
    assert response.json() == {"steps": 10, "loss_start": 2.0, "loss_end": 1.5}


def test_chat_skills_rejected_at_observe_level(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.autonomy_level", "observe")
    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"message": "hi", "session_id": "s-observe", "skills": True}
        )
    assert response.status_code == 400
    assert "autonomy level" in response.json()["detail"]


def test_chat_skills_allowed_at_assisted_level(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.autonomy_level", "assisted")

    class ScriptedBrain(Brain):
        name = "scripted-assisted"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            return "FINAL ANSWER: ok"

    monkeypatch.setattr(council, "_default_brain", ScriptedBrain())

    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"message": "hi", "session_id": "s-assisted", "skills": True}
        )
    assert response.status_code == 200


def test_chat_unreachable_brain_returns_clean_json_error(monkeypatch):
    """A brain call failing for any reason (Ollama down, model not pulled,
    a network error, ...) must come back as a JSON error the web GUI can
    parse — not an unhandled exception turning into a raw framework 500
    HTML page, which broke `response.json()` client-side with a confusing
    "Unexpected token" instead of showing the real problem."""

    class UnreachableBrain(Brain):
        name = "unreachable"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            raise ConnectionError("Connection refused")

    monkeypatch.setattr(council, "_default_brain", UnreachableBrain())

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "hi", "session_id": "s-down"})
    assert response.status_code == 502
    body = response.json()
    assert "detail" in body
    assert "Connection refused" in body["detail"]


def test_chat_council_and_skills_combine(monkeypatch):
    class ToolBrain(Brain):
        def __init__(self, name: str, final: str):
            self.name = name
            self._final = final
            self._calls = 0

        async def generate(self, messages: list[dict[str, str]]) -> str:
            self._calls += 1
            if self._calls == 1:
                return "ACTION: calculator: 1 + 1"
            return f"FINAL ANSWER: {self._final}"

    class EchoSynthesizer(Brain):
        name = "synthesizer"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            return messages[0]["content"]

    brains = {"a:1": ToolBrain("brain-a", "two"), "a:2": ToolBrain("brain-b", "also two")}
    monkeypatch.setattr("kafkaf.core.config.settings.council_brains", "a:1,a:2")
    monkeypatch.setattr(council, "get_brain", lambda spec: brains[spec])
    monkeypatch.setattr(council, "_default_brain", EchoSynthesizer())

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message": "what's 1+1?", "session_id": "s-combo", "council": True, "skills": True},
        )
    assert response.status_code == 200
    reply = response.json()["reply"]
    # Both council brains ran their tool-use loop to completion (their real
    # FINAL ANSWER made it through), not just their raw first ACTION line.
    assert "two" in reply
    assert "also two" in reply
    assert "ACTION" not in reply


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
