from pathlib import Path

from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings
from kafkaf.core.enrichment import store


def teach_fact(topic: str, fact: str) -> dict:
    """Store a raw, human-provided fact — no model call involved."""
    example_id = store.save_example(
        source_type="fact", topic=topic, prompt=topic, completion=fact
    )
    return {"id": example_id, "corpus_size": store.count_examples()}


async def distill_from_teacher(topic: str, teacher: Brain, instruction: str = "") -> dict:
    """Ask a teacher brain to explain a topic and store the captured completion.

    The completion is returned to the caller so the human can see exactly what
    got taught — enrichment should be visible, not a blind ingestion.
    """
    prompt = instruction or f"Explain: {topic}"
    completion = await teacher.generate([{"role": "user", "content": prompt}])
    example_id = store.save_example(
        source_type="distillation",
        topic=topic,
        prompt=prompt,
        completion=completion,
        teacher_name=teacher.name,
    )
    return {
        "id": example_id,
        "teacher": teacher.name,
        "completion": completion,
        "corpus_size": store.count_examples(),
    }


def run_training_step(steps: int = 50) -> dict:
    from kafkaf.model.train import train_step  # local import: torch is an optional dependency

    return train_step(steps=steps)


def get_status() -> dict:
    counts = store.count_examples()
    latest_run = store.get_latest_training_run()
    checkpoint_path = settings.own_model_checkpoint_path
    return {
        "corpus_size": counts["total"],
        "unused_examples": counts["unused"],
        "last_training_run": latest_run,
        "checkpoint_exists": Path(checkpoint_path).exists(),
        "checkpoint_path": checkpoint_path,
        "own_model_preset": settings.own_model_preset,
    }
