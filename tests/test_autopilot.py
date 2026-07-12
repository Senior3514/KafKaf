import pytest

torch = pytest.importorskip("torch")

from kafkaf.core.brains.base import Brain  # noqa: E402
from kafkaf.core.enrichment import autopilot, store  # noqa: E402


class FakeTeacher(Brain):
    name = "fake-teacher"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return f"fact about {messages[0]['content']}"


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


def test_run_forever_cycles_and_trains(monkeypatch):
    monkeypatch.setattr("kafkaf.core.enrichment.autopilot.get_brain", lambda spec: FakeTeacher())

    autopilot.run_forever(
        teacher="fake:whatever",
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
