"""Autonomous curriculum-learning loop: KafKaf's own model teaching itself
from a real teacher brain, one topic at a time, training periodically. This
is the piece that lets KafKaf "live on a VPS and keep growing on its own."

Deliberately paced, not "as fast as possible": an unattended loop hitting a
paid API or the CPU flat-out is a cost/stability risk, not a feature. Tune
the pacing options up once you trust the impact on your bill/hardware.
"""

import asyncio
import time

import typer

from kafkaf.core.brains.registry import get_brain
from kafkaf.core.config import settings
from kafkaf.core.enrichment import service
from kafkaf.core.enrichment import store as enrichment_store
from kafkaf.core.enrichment.topics import load_topics

app = typer.Typer(help="Run KafKaf's autonomous teach-and-train curriculum loop.")

DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_TRAIN_EVERY = 5
DEFAULT_TRAIN_STEPS = 100


def default_teacher() -> str:
    return f"ollama:{settings.ollama_model}"


def next_topic(topics: list[str], cycle: int) -> str:
    return topics[cycle % len(topics)]


def should_train(cycle: int, train_every: int) -> bool:
    return train_every > 0 and cycle % train_every == 0


async def teach_one(topic: str, teacher_spec: str) -> dict:
    if teacher_spec == "own":
        raise ValueError("autopilot needs a real teacher — 'own' is the model being trained.")
    brain = get_brain(teacher_spec)
    return await service.distill_from_teacher(topic, brain)


def run_forever(
    teacher: str,
    topics_path: str | None,
    interval_seconds: int,
    train_every: int,
    train_steps: int,
    max_cycles: int | None,
) -> None:
    enrichment_store.init_db()
    topics = load_topics(topics_path)

    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        topic = next_topic(topics, cycle)
        try:
            result = asyncio.run(teach_one(topic, teacher))
            print(
                f"[autopilot] taught {topic!r} from {result['teacher']} "
                f"(corpus={result['corpus_size']['total']})"
            )
        except Exception as exc:  # a bad teacher call must not kill the loop
            print(f"[autopilot] failed to teach {topic!r}: {exc}")

        cycle += 1
        if should_train(cycle, train_every):
            try:
                train_result = service.run_training_step(steps=train_steps)
                print(
                    f"[autopilot] trained {train_result['steps']} steps, "
                    f"loss {train_result['loss_start']:.4f} -> {train_result['loss_end']:.4f}"
                )
            except ValueError as exc:
                print(f"[autopilot] training skipped: {exc}")

        if max_cycles is None or cycle < max_cycles:
            time.sleep(interval_seconds)


@app.command()
def autopilot(
    teacher: str = typer.Option(None, help="Teacher brain spec, e.g. 'ollama:llama3'. Defaults to the configured Ollama model — free and local."),
    topics_file: str = typer.Option(None, help="Custom newline-separated topics file. Defaults to a small built-in curriculum."),
    interval_seconds: int = typer.Option(DEFAULT_INTERVAL_SECONDS, help="Pause between topics."),
    train_every: int = typer.Option(DEFAULT_TRAIN_EVERY, help="Run a training step every N topics taught."),
    train_steps: int = typer.Option(DEFAULT_TRAIN_STEPS, help="Training steps per training run."),
    max_cycles: int = typer.Option(None, help="Stop after N topics (omit to run forever)."),
) -> None:
    """Continuously teach-and-train KafKaf's own model, unattended."""
    run_forever(
        teacher or default_teacher(),
        topics_file,
        interval_seconds,
        train_every,
        train_steps,
        max_cycles,
    )


if __name__ == "__main__":
    app()
