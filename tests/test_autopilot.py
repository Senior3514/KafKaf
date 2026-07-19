import pytest

torch = pytest.importorskip("torch")

from kafkaf.core.audit import store as audit_store  # noqa: E402
from kafkaf.core.brains.base import Brain  # noqa: E402
from kafkaf.core.enrichment import autopilot, store  # noqa: E402


class FakeTeacher(Brain):
    name = "fake-teacher"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return f"fact about {messages[0]['content']}"


class SmartFakeTeacher(Brain):
    """Distinguishes a curriculum-growth prompt from a normal teach prompt."""

    name = "smart-fake-teacher"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        content = messages[0]["content"]
        if content.startswith("Suggest"):
            return "new topic one\nnew topic two\nnew topic three"
        return f"fact about {content}"


@pytest.fixture(autouse=True)
def _isolated_storage(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        "kafkaf.core.config.settings.own_model_checkpoint_path", str(tmp_path / "model.pt")
    )
    monkeypatch.setattr(
        "kafkaf.core.config.settings.skills_workspace_dir", str(tmp_path / "workspace")
    )
    store.init_db()
    yield


def test_next_topic_cycles():
    topics = ["a", "b", "c"]
    assert [autopilot.next_topic(topics, i) for i in range(5)] == ["a", "b", "c", "a", "b"]


def test_next_teacher_cycles():
    teachers = ["ollama:a", "ollama:b"]
    assert [autopilot.next_teacher(teachers, i) for i in range(4)] == [
        "ollama:a",
        "ollama:b",
        "ollama:a",
        "ollama:b",
    ]


def test_parse_teachers():
    assert autopilot.parse_teachers("ollama:a, ollama:b ,openai:gpt-4o-mini") == [
        "ollama:a",
        "ollama:b",
        "openai:gpt-4o-mini",
    ]


def test_should_train():
    assert [autopilot.should_train(i, 3) for i in range(1, 7)] == [
        False,
        False,
        True,
        False,
        False,
        True,
    ]


def test_should_train_disabled_when_zero():
    assert autopilot.should_train(3, 0) is False


@pytest.mark.asyncio
async def test_teach_one_uses_registry(monkeypatch):
    monkeypatch.setattr("kafkaf.core.enrichment.autopilot.get_brain", lambda spec: FakeTeacher())
    result = await autopilot.teach_one("some topic", "ollama:llama3")
    assert result["teacher"] == "fake-teacher"
    assert "some topic" in result["completion"]


@pytest.mark.asyncio
async def test_teach_one_rejects_own_as_teacher():
    with pytest.raises(ValueError):
        await autopilot.teach_one("some topic", "own")


@pytest.mark.asyncio
async def test_propose_topics_dedups_against_existing(monkeypatch):
    class ProposingTeacher(Brain):
        name = "proposer"

        async def generate(self, messages):
            return "existing topic\nNew Topic\nanother new one\n"

    monkeypatch.setattr(
        "kafkaf.core.enrichment.autopilot.get_brain", lambda spec: ProposingTeacher()
    )
    fresh = await autopilot.propose_topics("ollama:llama3", ["existing topic"], count=5)
    assert fresh == ["New Topic", "another new one"]


@pytest.mark.asyncio
async def test_propose_topics_rejects_own_as_teacher():
    with pytest.raises(ValueError):
        await autopilot.propose_topics("own", [])


def test_run_forever_rotates_teachers(monkeypatch):
    seen_specs = []

    def fake_get_brain(spec):
        seen_specs.append(spec)
        return FakeTeacher()

    monkeypatch.setattr("kafkaf.core.enrichment.autopilot.get_brain", fake_get_brain)

    autopilot.run_forever(
        teachers=["ollama:a", "ollama:b"],
        topics_path=None,
        interval_seconds=0,
        train_every=0,
        train_steps=10,
        max_cycles=4,
    )

    assert seen_specs == ["ollama:a", "ollama:b", "ollama:a", "ollama:b"]


def test_run_forever_cycles_and_trains(monkeypatch):
    monkeypatch.setattr("kafkaf.core.enrichment.autopilot.get_brain", lambda spec: FakeTeacher())

    autopilot.run_forever(
        teachers=["fake:whatever"],
        topics_path=None,
        interval_seconds=0,
        train_every=2,
        train_steps=10,
        max_cycles=4,
    )

    # 4 taught topics + 2 reflections (one after each of the two training
    # runs at cycles 2 and 4). The second reflection lands after the last
    # training run, so exactly one example is still unused at the end.
    counts = store.count_examples()
    assert counts["total"] == 6
    assert counts["unused"] == 1

    latest = store.get_latest_training_run()
    assert latest is not None
    assert latest["steps"] == 10
    # cycle-4 run trains the 2 new topics plus the cycle-2 reflection
    assert latest["num_examples"] == 3

    event_types = {e["event_type"] for e in audit_store.recent_events(limit=100)}
    assert "autopilot_teach" in event_types
    assert "autopilot_train" in event_types
    assert "autopilot_reflection" in event_types
    # Default identity_refresh_every is 3; only 2 training rounds here, so
    # no identity refresh should have fired yet.
    assert "autopilot_identity_refresh" not in event_types


def test_run_forever_refreshes_identity_on_interval(monkeypatch):
    monkeypatch.setattr(
        "kafkaf.core.enrichment.autopilot.get_brain", lambda spec: SmartFakeTeacher()
    )

    autopilot.run_forever(
        teachers=["fake:whatever"],
        topics_path=None,
        interval_seconds=0,
        train_every=1,
        train_steps=10,
        max_cycles=3,
        identity_refresh_every=3,
    )

    event_types = [e["event_type"] for e in audit_store.recent_events(limit=100)]
    # 3 training rounds, refresh every 3 -> exactly one identity refresh.
    assert event_types.count("autopilot_identity_refresh") == 1

    # And it actually wrote the identity file, not just logged. The fake
    # teacher prefixes "fact about " to whatever prompt it's given, so its
    # presence in the stored file proves the teacher's output was persisted
    # (a fresh, never-written identity file would not contain it).
    import asyncio

    from kafkaf.core.skills.identity import IdentitySkill

    stored = asyncio.run(IdentitySkill().run("show"))
    assert stored.startswith("fact about ")


def test_run_forever_identity_refresh_disabled_when_zero(monkeypatch):
    monkeypatch.setattr(
        "kafkaf.core.enrichment.autopilot.get_brain", lambda spec: SmartFakeTeacher()
    )

    autopilot.run_forever(
        teachers=["fake:whatever"],
        topics_path=None,
        interval_seconds=0,
        train_every=1,
        train_steps=10,
        max_cycles=3,
        identity_refresh_every=0,
    )

    event_types = {e["event_type"] for e in audit_store.recent_events(limit=100)}
    assert "autopilot_identity_refresh" not in event_types


def test_run_forever_logs_stop_event(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.enrichment.autopilot.get_brain", lambda spec: FakeTeacher())
    stop_file = str(tmp_path / "autopilot.stop")
    (tmp_path / "autopilot.stop").touch()

    autopilot.run_forever(
        teachers=["fake:whatever"],
        topics_path=None,
        interval_seconds=0,
        train_every=0,
        train_steps=10,
        max_cycles=5,
        stop_file=stop_file,
    )

    events = audit_store.recent_events(limit=100)
    assert any(e["event_type"] == "autopilot_stop" for e in events)


def test_is_stop_requested(tmp_path):
    stop_file = str(tmp_path / "autopilot.stop")
    assert autopilot.is_stop_requested(stop_file) is False
    (tmp_path / "autopilot.stop").touch()
    assert autopilot.is_stop_requested(stop_file) is True


def test_interruptible_sleep_returns_immediately_without_stop(tmp_path):
    stop_file = str(tmp_path / "autopilot.stop")
    assert autopilot._interruptible_sleep(0, stop_file) is False


def test_interruptible_sleep_stops_early(tmp_path):
    stop_file = str(tmp_path / "autopilot.stop")
    (tmp_path / "autopilot.stop").touch()
    # would normally sleep 300s — must return almost immediately once stopped
    assert autopilot._interruptible_sleep(300, stop_file) is True


def test_run_forever_halts_immediately_if_already_stopped(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.enrichment.autopilot.get_brain", lambda spec: FakeTeacher())
    stop_file = str(tmp_path / "autopilot.stop")
    (tmp_path / "autopilot.stop").touch()

    autopilot.run_forever(
        teachers=["fake:whatever"],
        topics_path=None,
        interval_seconds=0,
        train_every=0,
        train_steps=10,
        max_cycles=5,
        stop_file=stop_file,
    )

    # nothing should have been taught — the stop was seen before the first cycle
    assert store.count_examples()["total"] == 0


@pytest.mark.asyncio
async def test_reflect_on_progress_stores_lesson_in_corpus(monkeypatch):
    class ReflectiveTeacher(Brain):
        name = "reflective-teacher"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            assert "training run" in messages[0]["content"]
            return "The common thread is that structured practice compounds."

    monkeypatch.setattr(
        "kafkaf.core.enrichment.autopilot.get_brain", lambda spec: ReflectiveTeacher()
    )
    reflection = await autopilot.reflect_on_progress(
        "ollama:llama3", ["photosynthesis", "gravity"], {"loss_start": 2.0, "loss_end": 1.5}
    )
    assert "compounds" in reflection
    examples = store.get_unused_examples()
    assert any("compounds" in e["completion"] for e in examples)


@pytest.mark.asyncio
async def test_reflect_on_progress_rejects_own_as_teacher():
    with pytest.raises(ValueError):
        await autopilot.reflect_on_progress("own", [], {"loss_start": 1.0, "loss_end": 0.9})


@pytest.mark.asyncio
async def test_refresh_identity_folds_reflections_into_the_file(monkeypatch):
    from kafkaf.core.skills.identity import IdentitySkill

    class IdentityTeacher(Brain):
        name = "identity-teacher"

        async def generate(self, messages: list[dict[str, str]]) -> str:
            # Confirm the current description and the reflections both reach the teacher.
            content = messages[0]["content"]
            assert "self-description" in content
            assert "structured practice compounds" in content
            return "A curious assistant that has learned structured practice compounds over time."

    monkeypatch.setattr(
        "kafkaf.core.enrichment.autopilot.get_brain", lambda spec: IdentityTeacher()
    )
    updated = await autopilot.refresh_identity(
        "ollama:llama3", ["structured practice compounds"]
    )
    assert "structured practice compounds" in updated
    # And it was actually persisted to the identity file, not just returned.
    stored = await IdentitySkill().run("show")
    assert "structured practice compounds" in stored


@pytest.mark.asyncio
async def test_refresh_identity_rejects_own_as_teacher():
    with pytest.raises(ValueError):
        await autopilot.refresh_identity("own", [])


def test_default_stop_file_matches_running_container_env(monkeypatch):
    """Real bug found by tracing the docs: docker-compose.autopilot.yml
    starts the loop with --stop-file /data/autopilot.stop, but the
    documented convenience command `docker compose exec autopilot
    kafkaf-autopilot-ctl stop` never passes --stop-file — so without this,
    the CLI default would silently touch the wrong file (relative to the
    container's /app cwd), and the loop would never see the stop request.
    Since `exec` runs in the same container with the same environment,
    reading AUTOPILOT_STOP_FILE (already set by compose on that container)
    makes the default correct without needing to remember the flag."""
    monkeypatch.delenv("AUTOPILOT_STOP_FILE", raising=False)
    assert autopilot._default_stop_file() == autopilot.DEFAULT_STOP_FILE

    monkeypatch.setenv("AUTOPILOT_STOP_FILE", "/data/autopilot.stop")
    assert autopilot._default_stop_file() == "/data/autopilot.stop"


def test_ctl_stop_resume_status(tmp_path, capsys):
    stop_file = str(tmp_path / "autopilot.stop")

    autopilot.status(stop_file=stop_file)
    assert "not stopped" in capsys.readouterr().out

    autopilot.stop(stop_file=stop_file)
    assert autopilot.is_stop_requested(stop_file) is True

    autopilot.status(stop_file=stop_file)
    assert "STOPPED" in capsys.readouterr().out

    autopilot.resume(stop_file=stop_file)
    assert autopilot.is_stop_requested(stop_file) is False


def test_run_forever_dynamic_curriculum_grows(monkeypatch, tmp_path):
    topics_file = tmp_path / "topics.txt"
    topics_file.write_text("topic a\ntopic b\n")

    monkeypatch.setattr(
        "kafkaf.core.enrichment.autopilot.get_brain", lambda spec: SmartFakeTeacher()
    )

    autopilot.run_forever(
        teachers=["ollama:a"],
        topics_path=str(topics_file),
        interval_seconds=0,
        train_every=0,
        train_steps=10,
        max_cycles=3,
        dynamic_curriculum=True,
    )

    # cycle 2 (0-indexed, third iteration) wraps the 2-topic list and should
    # trigger growth, teaching a freshly-proposed topic on the third call.
    examples = store.get_unused_examples()
    topics_taught = {example["topic"] for example in examples}
    assert "new topic one" in topics_taught
