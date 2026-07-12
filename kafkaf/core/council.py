"""The single seam where a chat turn is resolved.

Routes to one configured brain by default. Council mode fans the same
query out to several brains in parallel and synthesizes their answers into
one — an honest "council of brains" (the Mixture-of-Agents pattern:
combining existing models' answers, not creating new general capability
beyond what they already contain — see docs/ROADMAP.md's vision section).
"""

import asyncio

from kafkaf.core.brains.base import Brain
from kafkaf.core.brains.ollama_brain import OllamaBrain
from kafkaf.core.brains.registry import get_brain
from kafkaf.core.memory import store
from kafkaf.core.personas.default import get_persona

_default_brain: Brain = OllamaBrain()


async def _gather_answers(
    brain_specs: list[str], messages: list[dict[str, str]]
) -> list[dict[str, str]]:
    brains = [get_brain(spec) for spec in brain_specs]
    results = await asyncio.gather(
        *(brain.generate(messages) for brain in brains), return_exceptions=True
    )

    answers = []
    for spec, brain, result in zip(brain_specs, brains, results):
        if isinstance(result, Exception):
            continue
        answers.append({"spec": spec, "brain": brain.name, "answer": result})
    return answers


async def council_chat(
    messages: list[dict[str, str]], brain_specs: list[str], synthesizer: Brain
) -> str:
    """Fan a query out to several brains in parallel, then synthesize one
    final answer from whichever of them actually responded."""
    answers = await _gather_answers(brain_specs, messages)
    if not answers:
        raise RuntimeError("All council brains failed to respond.")
    if len(answers) == 1:
        return answers[0]["answer"]

    joined = "\n\n".join(f"[{answer['brain']}]: {answer['answer']}" for answer in answers)
    synthesis_prompt = (
        "You were given the same question independently by several AI models. "
        "Combine their answers into one clear, accurate final answer. Resolve any "
        "disagreements using your own judgment, don't mention that this is a "
        "synthesis, and keep it concise.\n\n" + joined
    )
    return await synthesizer.generate([{"role": "user", "content": synthesis_prompt}])


async def handle_chat(
    session_id: str,
    message: str,
    persona_key: str = "default",
    brain: Brain | None = None,
    council_brains: list[str] | None = None,
) -> str:
    persona = get_persona(persona_key)
    history = store.get_history(session_id)
    messages = [
        {"role": "system", "content": persona.system_prompt},
        *history,
        {"role": "user", "content": message},
    ]

    if council_brains:
        synthesizer = brain or _default_brain
        reply = await council_chat(messages, council_brains, synthesizer)
    else:
        active_brain = brain or _default_brain
        reply = await active_brain.generate(messages)

    store.save_message(session_id, "user", message)
    store.save_message(session_id, "assistant", reply)
    return reply
