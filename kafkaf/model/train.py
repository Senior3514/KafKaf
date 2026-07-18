from dataclasses import asdict
from pathlib import Path

import torch
import typer

from kafkaf.core.config import settings
from kafkaf.core.enrichment import store as enrichment_store
from kafkaf.model import dataset
from kafkaf.model.config import GPTConfig, get_preset
from kafkaf.model.gpt import GPT

app = typer.Typer(help="Train KafKaf's own model.")


def _device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load_or_init_model(checkpoint_path: str, preset_name: str) -> tuple[GPT, GPTConfig]:
    path = Path(checkpoint_path)
    if path.exists():
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        config = GPTConfig(**checkpoint["config"])
        model = GPT(config)
        model.load_state_dict(checkpoint["model"])
        return model, config

    config = get_preset(preset_name)
    return GPT(config), config


def train_step(
    steps: int = 50,
    batch_size: int = 8,
    lr: float = 3e-4,
    checkpoint_path: str | None = None,
    preset: str | None = None,
) -> dict:
    """Run a handful of training steps on unused corpus examples, continuing from
    the last checkpoint if one exists — this is the "teach and feed it" loop."""
    checkpoint_path = checkpoint_path or settings.own_model_checkpoint_path
    preset = preset or settings.own_model_preset

    examples = enrichment_store.get_unused_examples()
    if not examples:
        raise ValueError("No unused corpus examples — teach the model something first.")

    device = _device()
    model, config = _load_or_init_model(checkpoint_path, preset)
    model.to(device)
    model.train()

    data = dataset.examples_to_byte_stream(examples)
    if len(data) <= config.block_size:
        raise ValueError(
            f"Corpus too small ({len(data)} bytes) for block_size={config.block_size} — "
            "teach a few more/longer examples first."
        )

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)

    loss_start: float | None = None
    loss_end: float | None = None
    for step in range(steps):
        x, y = dataset.get_batch(data, config.block_size, batch_size, device=device)
        _, loss = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()

        loss_value = loss.item()
        if step == 0:
            loss_start = loss_value
        loss_end = loss_value

    Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model.state_dict(), "config": asdict(config)}, checkpoint_path)

    example_ids = [example["id"] for example in examples]
    run_id = enrichment_store.save_training_run(
        num_examples=len(examples),
        steps=steps,
        loss_start=loss_start,
        loss_end=loss_end,
        checkpoint_path=checkpoint_path,
    )
    enrichment_store.mark_examples_trained(example_ids, run_id)

    return {
        "run_id": run_id,
        "steps": steps,
        "num_examples": len(examples),
        "loss_start": loss_start,
        "loss_end": loss_end,
        "checkpoint_path": checkpoint_path,
        "param_count": model.num_params(),
        "device": device,
    }


@app.command("train")
def train_cli(
    steps: int = typer.Option(50, help="Number of training steps to run."),
    batch_size: int = typer.Option(8, help="Batch size."),
    lr: float = typer.Option(3e-4, help="Learning rate."),
) -> None:
    """`kafkaf model train --steps 200` — standalone/scheduled training run."""
    result = train_step(steps=steps, batch_size=batch_size, lr=lr)
    typer.echo(
        f"Trained {result['steps']} steps on {result['num_examples']} examples. "
        f"Loss {result['loss_start']:.4f} -> {result['loss_end']:.4f}. "
        f"Checkpoint: {result['checkpoint_path']} "
        f"({result['param_count']:,} params, {result['device']})"
    )


if __name__ == "__main__":
    app()
