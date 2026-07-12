import pytest

torch = pytest.importorskip("torch")

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

    counts = store.count_examples()
    assert counts["total"] == 4
    assert counts["unused"] == 0

    latest = store.get_latest_training_run()
    assert latest is not None
    assert latest["steps"] == 10
    assert latest["num_examples"] == 2


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
