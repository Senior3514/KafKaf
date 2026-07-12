"""Autonomous curriculum-learning loop: KafKaf's own model being taught by
one or more teacher brains, one topic at a time, training periodically.
This is the piece that lets KafKaf "live on a VPS and keep growing on its
own." Supports rotating through multiple teacher models, and (optionally)
letting a teacher propose new curriculum topics once the starting list is
exhausted — real autonomous curriculum growth, driven by a capable teacher
model, not the small owned model directing its own training (which would
be far too weak to do anything useful there).

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
DEFAULT_TOPICS_PER_GROWTH = 5


def default_teachers() -> list[str]:
    return [f"ollama:{settings.ollama_model}"]


def parse_teachers(spec: str) -> list[str]:
    return [t.strip() for t in spec.split(",") if t.strip()]


def next_topic(topics: list[str], cycle: int) -> str:
    return topics[cycle % len(topics)]


def next_teacher(teachers: list[str], cycle: int) -> str:
    return teachers[cycle % len(teachers)]


def should_train(cycle: int, train_every: int) -> bool:
    return train_every > 0 and cycle % train_every == 0


async def teach_one(topic: str, teacher_spec: str) -> dict:
    if teacher_spec == "own":
        raise ValueError("autopilot needs a real teacher — 'own' is the model being trained.")
    brain = get_brain(teacher_spec)
    return await service.distill_from_teacher(topic, brain)


async def propose_topics(
    teacher_spec: str, existing_topics: list[str], count: int = DEFAULT_TOPICS_PER_GROWTH
) -> list[str]:
    """Ask a teacher model to propose new curriculum topics not yet covered."""
    if teacher_spec == "own":
        raise ValueError("curriculum growth needs a real teacher — 'own' is the model being trained.")
    brain = get_brain(teacher_spec)
    recent = existing_topics[-30:]
    listed = "\n".join(f"- {t}" for t in recent)
    prompt = (
        f"Suggest {count} short, distinct topics (one per line, no numbering or extra text) "
        "that would help a small private assistant model become more broadly useful. "
        f"Do not repeat any of these already-covered topics:\n{listed}"
    )
    reply = await brain.generate([{"role": "user", "content": prompt}])

    seen = {t.lower() for t in existing_topics}
    fresh: list[str] = []
    for line in reply.splitlines():
        topic = line.strip("-*• \t")
        key = topic.lower()
        if topic and key not in seen:
            fresh.append(topic)
            seen.add(key)
    return fresh[:count]


def run_forever(
    teachers: list[str],
    topics_path: str | None,
    interval_seconds: int,
    train_every: int,
    train_steps: int,
    max_cycles: int | None,
    dynamic_curriculum: bool = False,
    topics_per_growth: int = DEFAULT_TOPICS_PER_GROWTH,
) -> None:
    enrichment_store.init_db()
    topics = load_topics(topics_path)

    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        if dynamic_curriculum and cycle > 0 and cycle % len(topics) == 0:
            growth_teacher = next_teacher(teachers, cycle)
            try:
                new_topics = asyncio.run(propose_topics(growth_teacher, topics, topics_per_growth))
                if new_topics:
                    topics.extend(new_topics)
                    print(
                        f"[autopilot] curriculum grew by {len(new_topics)} topics "
                        f"via {growth_teacher}: {new_topics}"
                    )
            except Exception as exc:  # a bad growth call must not kill the loop
                print(f"[autopilot] curriculum growth failed: {exc}")

        topic = next_topic(topics, cycle)
        teacher = next_teacher(teachers, cycle)
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
    teacher: str = typer.Option(
        None,
        help="Comma-separated teacher specs to rotate through, e.g. "
        "'ollama:llama3,ollama:qwen2.5:3b'. Defaults to the configured Ollama model.",
    ),
    topics_file: str = typer.Option(None, help="Custom newline-separated topics file. Defaults to a small built-in curriculum."),
    interval_seconds: int = typer.Option(DEFAULT_INTERVAL_SECONDS, help="Pause between topics."),
    train_every: int = typer.Option(DEFAULT_TRAIN_EVERY, help="Run a training step every N topics taught."),
    train_steps: int = typer.Option(DEFAULT_TRAIN_STEPS, help="Training steps per training run."),
    max_cycles: int = typer.Option(None, help="Stop after N topics (omit to run forever)."),
    dynamic_curriculum: bool = typer.Option(
        False,
        "--dynamic-curriculum",
        help="Once the topic list is exhausted, ask the teacher to propose new topics instead of repeating.",
    ),
    topics_per_growth: int = typer.Option(
        DEFAULT_TOPICS_PER_GROWTH, help="How many new topics to request per curriculum growth round."
    ),
) -> None:
    """Continuously teach-and-train KafKaf's own model, unattended."""
    teachers = parse_teachers(teacher) if teacher else default_teachers()
    run_forever(
        teachers,
        topics_file,
        interval_seconds,
        train_every,
        train_steps,
        max_cycles,
        dynamic_curriculum,
        topics_per_growth,
    )


if __name__ == "__main__":
    app()
