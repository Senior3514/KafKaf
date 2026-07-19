"""The single seam where a chat turn is resolved.

Routes to one configured brain by default. Council mode fans the same
query out to several brains in parallel and synthesizes their answers into
one — an honest "council of brains" (the Mixture-of-Agents pattern:
combining existing models' answers, not creating new general capability
beyond what they already contain — see docs/ROADMAP.md's vision section).

A turn can pause mid-way if a brain requests an approval-gated skill
(run_code, browser_automate) — see resume_chat, which continues a paused
turn after a live human approves or denies it out-of-band.
"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass

from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.base import Brain
from kafkaf.core.brains.ollama_brain import OllamaBrain
from kafkaf.core.brains.registry import get_brain
from kafkaf.core.memory import store
from kafkaf.core.personas.default import get_persona
from kafkaf.core.skills import store as skills_store
from kafkaf.core.skills.loop import SKILLS_BY_NAME, resume_skill_loop, run_skill_loop

_default_brain: Brain = OllamaBrain()


class ApprovalNotFoundError(Exception):
    """No pending approval exists with the given id."""


class ApprovalAlreadyDecidedError(Exception):
    """The approval was already approved/denied (or raced and lost)."""


@dataclass
class ChatOutcome:
    session_id: str
    reply: str | None = None
    pending_approval: dict | None = None  # {"approval_id", "skill_name", "skill_arg"}


def _finalize(session_id: str, message: str, event_type: str, actor: str, reply: str, duration_ms: int) -> None:
    """Only ever called with a real final reply — never on a pause, so an
    abandoned/never-decided turn never pollutes chat history."""
    audit_store.log_event(
        event_type, actor, f"session={session_id} msg_chars={len(message)} reply_chars={len(reply)}", duration_ms
    )
    store.save_message(session_id, "user", message)
    store.save_message(session_id, "assistant", reply)


async def _gather_answers(
    brain_specs: list[str], messages: list[dict[str, str]], use_skills: bool = False
) -> list[dict[str, str]]:
    brains = [get_brain(spec) for spec in brain_specs]

    async def _call(brain: Brain) -> str:
        if not use_skills:
            return await brain.generate(messages)
        # Council brains never pause for approval — see run_skill_loop's
        # allow_pause=False handling (auto-denies a requires_approval
        # skill with a clear observation instead of hanging the fan-out).
        result = await run_skill_loop(brain, messages, allow_pause=False)
        return result.reply

    calls = (_call(brain) for brain in brains)
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
    brain_spec: str | None = None,
    council_brains: list[str] | None = None,
    use_skills: bool = False,
) -> ChatOutcome:
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
        duration_ms = int((time.monotonic() - start) * 1000)
        _finalize(session_id, message, event_type, actor, reply, duration_ms)
        return ChatOutcome(session_id=session_id, reply=reply)

    if use_skills:
        active_brain = brain or _default_brain
        result = await run_skill_loop(
            active_brain, messages, session_id=session_id, user_message=message, brain_spec=brain_spec
        )
        if result.pending_approval:
            return ChatOutcome(session_id=session_id, pending_approval=asdict(result.pending_approval))
        duration_ms = int((time.monotonic() - start) * 1000)
        _finalize(session_id, message, "chat_skills", active_brain.name, result.reply, duration_ms)
        return ChatOutcome(session_id=session_id, reply=result.reply)

    active_brain = brain or _default_brain
    reply = await active_brain.generate(messages)
    duration_ms = int((time.monotonic() - start) * 1000)
    _finalize(session_id, message, "chat", active_brain.name, reply, duration_ms)
    return ChatOutcome(session_id=session_id, reply=reply)


async def resume_chat(approval_id: int, decision: str) -> ChatOutcome:
    """Continue a paused turn after a live human approved or denied a
    requires_approval skill call. decision is "approved" or "denied"."""
    row = skills_store.claim_approval(approval_id, decision)
    if row is None:
        existing = skills_store.get_approval(approval_id)
        if existing is None:
            raise ApprovalNotFoundError(f"no such approval #{approval_id}")
        raise ApprovalAlreadyDecidedError(f"approval #{approval_id} was already {existing['status']}")

    conversation = json.loads(row["conversation_json"])
    skill = SKILLS_BY_NAME.get(row["skill_name"])
    start = time.monotonic()

    if decision == "approved":
        if skill is None:
            observation = f"error: unknown tool {row['skill_name']!r}"
            audit_store.log_event("skill_error", row["skill_name"], observation)
        else:
            try:
                observation = await skill.run(row["skill_arg"])
                duration_ms = int((time.monotonic() - start) * 1000)
                audit_store.log_event(
                    "skill_write",
                    row["skill_name"],
                    f"approved arg={row['skill_arg'][:100]!r} -> {observation[:100]!r}",
                    duration_ms,
                )
            except Exception as exc:
                observation = f"error: {exc}"
                audit_store.log_event("skill_error", row["skill_name"], f"approved but failed: {exc}")
    else:
        observation = f"error: user denied this action ({row['skill_name']}: {row['skill_arg']})"
        audit_store.log_event("skill_write_blocked", row["skill_name"], "denied by user")

    conversation.append({"role": "user", "content": f"OBSERVATION: {observation}"})
    brain = get_brain(row["brain_spec"]) if row["brain_spec"] else _default_brain
    result = await resume_skill_loop(
        brain,
        conversation,
        row["iterations_used"],
        session_id=row["session_id"],
        user_message=row["user_message"],
        brain_spec=row["brain_spec"],
    )

    if result.pending_approval:
        return ChatOutcome(session_id=row["session_id"], pending_approval=asdict(result.pending_approval))
    duration_ms = int((time.monotonic() - start) * 1000)
    _finalize(row["session_id"], row["user_message"], "chat_skills", brain.name, result.reply, duration_ms)
    return ChatOutcome(session_id=row["session_id"], reply=result.reply)
