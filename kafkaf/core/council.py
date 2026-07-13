"""The single seam where a chat turn is resolved.

Routes to one configured brain by default. Council mode fans the same
query out to several brains in parallel and synthesizes their answers into
one — an honest "council of brains" (the Mixture-of-Agents pattern:
combining existing models' answers, not creating new general capability
beyond what they already contain — see docs/ROADMAP.md's vision section).
"""

import asyncio
import time

from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.base import Brain
from kafkaf.core.brains.ollama_brain import OllamaBrain
from kafkaf.core.brains.registry import get_brain
from kafkaf.core.memory import store
from kafkaf.core.personas.default import get_persona
from kafkaf.core.skills.loop import run_skill_loop

_default_brain: Brain = OllamaBrain()


async def _gather_answers(
    brain_specs: list[str], messages: list[dict[str, str]], use_skills: bool = False
) -> list[dict[str, str]]:
    brains = [get_brain(spec) for spec in brain_specs]
    calls = (
        (run_skill_loop(brain, messages) if use_skills else brain.generate(messages))
        for brain in brains
    )
    results = await asyncio.gather(*calls, return_exceptions=True)

    answers = []
    for spec, brain, result in zip(brain_specs, brains, results):
        if isinstance(result, Exception):
            continue
        answers.append({"spec": spec, "brain": brain.name, "answer": result})
    return answers


async def council_chat(
    messages: list[dict[str, str]],
    brain_specs: list[str],
    synthesizer: Brain,
    use_skills: bool = False,
) -> str:
    """Fan a query out to several brains in parallel, then synthesize one
    final answer from whichever of them actually responded. With
    use_skills=True, each brain runs the ReAct tool-use loop independently
    before its answer is collected — a real combination of "several models"
    and "each can use tools," not a silent no-op for one or the other."""
    answers = await _gather_answers(brain_specs, messages, use_skills)
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
    use_skills: bool = False,
) -> str:
    persona = get_persona(persona_key)
    history = store.get_history(session_id)
    messages = [
        {"role": "system", "content": persona.system_prompt},
        *history,
        {"role": "user", "content": message},
    ]

    start = time.monotonic()
    if council_brains:
        event_type = "chat_council_skills" if use_skills else "chat_council"
        actor = ",".join(council_brains)
        synthesizer = brain or _default_brain
        reply = await council_chat(messages, council_brains, synthesizer, use_skills=use_skills)
    elif use_skills:
        active_brain = brain or _default_brain
        event_type, actor = "chat_skills", active_brain.name
        reply = await run_skill_loop(active_brain, messages)
    else:
        active_brain = brain or _default_brain
        event_type, actor = "chat", active_brain.name
        reply = await active_brain.generate(messages)
    duration_ms = int((time.monotonic() - start) * 1000)

    audit_store.log_event(
        event_type,
        actor,
        f"session={session_id} msg_chars={len(message)} reply_chars={len(reply)}",
        duration_ms,
    )
    store.save_message(session_id, "user", message)
    store.save_message(session_id, "assistant", reply)
    return reply
