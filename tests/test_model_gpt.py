import pytest

torch = pytest.importorskip("torch")

from kafkaf.core.enrichment import service, store  # noqa: E402
from kafkaf.model import train  # noqa: E402
from kafkaf.model.config import GPTConfig  # noqa: E402
from kafkaf.model.gpt import GPT  # noqa: E402

FACTS = [
    ("KafKaf", "KafKaf is a free, private, self-hosted AI agent platform."),
    ("privacy", "KafKaf keeps everything local by default, nothing leaves your machine."),
    ("teachers", "KafKaf's own model can be taught by other local or API models."),
    ("training", "KafKaf's own model is trained from scratch, not a repackaged checkpoint."),
    ("growth", "KafKaf's own model keeps learning over time through continual training."),
]


@pytest.fixture(autouse=True)
def _isolated_storage(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        "kafkaf.core.config.settings.own_model_checkpoint_path", str(tmp_path / "model.pt")
    )
    store.init_db()
    yield


def test_gpt_forward_and_generate():
    torch.manual_seed(0)
    config = GPTConfig(vocab_size=256, block_size=16, n_layer=1, n_head=1, n_embd=8)
    model = GPT(config)

    idx = torch.randint(0, config.vocab_size, (2, config.block_size))
    logits, loss = model(idx, targets=idx)
    assert logits.shape == (2, config.block_size, config.vocab_size)
    assert loss.item() > 0

    out = model.generate(idx[:, :4], max_new_tokens=5)
    assert out.shape == (2, 9)


def test_train_step_reduces_loss():
    torch.manual_seed(0)
    for topic, fact in FACTS:
        service.teach_fact(topic, fact)

    result = train.train_step(steps=40, batch_size=2)

    assert result["loss_end"] < result["loss_start"]
    assert result["num_examples"] == len(FACTS)
    assert store.count_examples()["unused"] == 0


def test_train_step_requires_examples():
    with pytest.raises(ValueError):
        train.train_step(steps=5)
