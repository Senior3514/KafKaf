"""KafKaf's local enrichment MCP server.

Runs over stdio — the standard transport for local Claude Desktop/Code
integration. No network port, no auth surface: the simplest possible fit for
a single-user, local, private setup.
"""

import asyncio

from mcp.server.fastmcp import FastMCP

from kafkaf.core import council
from kafkaf.core.brains.own_model_brain import OwnModelBrain
from kafkaf.core.brains.registry import get_brain
from kafkaf.core.enrichment import service
from kafkaf.core.enrichment import store as enrichment_store
from kafkaf.core.memory import store as memory_store

app = FastMCP("kafkaf-enrichment")


@app.tool()
def teach_fact(topic: str, fact: str) -> str:
    """Teach KafKaf's own model a raw fact directly — no teacher model involved."""
    result = service.teach_fact(topic, fact)
    counts = result["corpus_size"]
    return f"Taught: {topic!r}. Corpus size: {counts['total']} ({counts['unused']} unused)."


@app.tool()
async def distill_from_teacher(topic: str, teacher: str, instruction: str = "") -> str:
    """Ask a teacher model to explain a topic, and store its answer as training data.

    teacher examples: 'ollama:llama3', 'openai:gpt-4o-mini',
    'anthropic:claude-3-5-haiku-latest', 'gemini:gemini-1.5-flash'.
    """
    try:
        brain = get_brain(teacher)
    except ValueError as exc:
        return f"Error: {exc}"

    try:
        result = await service.distill_from_teacher(topic, brain, instruction)
    except Exception as exc:  # teacher call failed: bad key, network, rate limit, ...
        return f"Error asking {teacher}: {exc}"

    counts = result["corpus_size"]
    return (
        f"Learned from {result['teacher']} about {topic!r}:\n\n{result['completion']}\n\n"
        f"Corpus size: {counts['total']} ({counts['unused']} unused)."
    )


@app.tool()
async def train_step(steps: int = 50) -> str:
    """Run training steps on unused corpus examples, continuing from the last checkpoint.

    Can take a while for larger step counts; runs off the main event loop.
    """
    try:
        result = await asyncio.to_thread(service.run_training_step, steps)
    except ValueError as exc:
        return f"Error: {exc}"

    return (
        f"Trained {result['steps']} steps on {result['num_examples']} examples. "
        f"Loss {result['loss_start']:.4f} -> {result['loss_end']:.4f}. "
        f"Checkpoint: {result['checkpoint_path']} "
        f"({result['param_count']:,} params, {result['device']})."
    )


@app.tool()
def status() -> str:
    """Report the current corpus size, last training run, and checkpoint status."""
    info = service.get_status()
    last_run = info["last_training_run"]
    last_run_text = (
        f"run #{last_run['id']}: {last_run['steps']} steps, "
        f"loss {last_run['loss_start']:.4f} -> {last_run['loss_end']:.4f} "
        f"({last_run['created_at']})"
        if last_run
        else "none yet"
    )
    checkpoint_state = "exists" if info["checkpoint_exists"] else "not trained yet"
    return (
        f"Corpus: {info['corpus_size']} examples ({info['unused_examples']} not yet trained on).\n"
        f"Checkpoint: {info['checkpoint_path']} "
        f"({checkpoint_state}, preset={info['own_model_preset']}).\n"
        f"Last training run: {last_run_text}"
    )


@app.tool()
async def chat_with_own_model(message: str, session_id: str = "mcp-own-model") -> str:
    """Chat directly with KafKaf's own trained model.

    Quality reflects how much it has been taught and trained so far — it
    starts weak and grows over time, this is expected.
    """
    try:
        return await council.handle_chat(session_id, message, brain=OwnModelBrain())
    except RuntimeError as exc:
        return f"Error: {exc}"


def main() -> None:
    memory_store.init_db()
    enrichment_store.init_db()
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
