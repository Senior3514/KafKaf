import pytest

from kafkaf.core.brains.base import Brain
from kafkaf.core.enrichment import service, store


class FakeTeacher(Brain):
    name = "fake-teacher"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return "the answer"


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    store.init_db()
    yield


def test_teach_fact_and_status():
    result = service.teach_fact("topic", "a fact")
    assert result["corpus_size"] == {"total": 1, "unused": 1}

    examples = store.get_unused_examples()
    assert len(examples) == 1
    assert examples[0]["topic"] == "topic"
    assert examples[0]["completion"] == "a fact"


def test_mark_examples_trained():
    example_id = store.save_example("fact", "t", "t", "c")
    run_id = store.save_training_run(
        num_examples=1, steps=10, loss_start=2.0, loss_end=1.0, checkpoint_path="x.pt"
    )
    store.mark_examples_trained([example_id], run_id)

    assert store.count_examples() == {"total": 1, "unused": 0}
    latest = store.get_latest_training_run()
    assert latest["id"] == run_id
    assert latest["loss_start"] == 2.0
    assert latest["loss_end"] == 1.0


@pytest.mark.asyncio
async def test_distill_from_teacher():
    result = await service.distill_from_teacher("topic", FakeTeacher())
    assert result["completion"] == "the answer"
    assert result["teacher"] == "fake-teacher"
    assert result["corpus_size"]["total"] == 1


def test_get_status_no_training_yet():
    service.teach_fact("topic", "a fact")
    status = service.get_status()
    assert status["corpus_size"] == 1
    assert status["unused_examples"] == 1
    assert status["last_training_run"] is None
    assert status["checkpoint_exists"] is False
