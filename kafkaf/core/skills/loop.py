"""A brain-agnostic tool-use loop — the ReAct pattern (Yao et al. 2022,
"ReAct: Synergizing Reasoning and Acting in Language Models," arXiv:2210.03629).

Deliberately text-protocol based rather than provider-specific function-
calling APIs: every Brain's generate() only ever sees/returns plain text
messages, so skills work uniformly across Ollama, every API brain, and
(once it's capable enough) the small owned model too — no per-provider
special-casing of the Brain interface required.

A subset of skills (Skill.requires_approval) never auto-execute here —
they pause the loop and hand back a PendingApproval instead, persisted via
core/skills/store.py, so a live human can approve or deny out-of-band
(see core/council.py's resume_chat and the /skills/approvals/* API). This
makes the loop resumable an arbitrary number of times, not a one-shot
special case: resuming may itself hit another approval-gated action.
"""

import json
import re
import time
from dataclasses import dataclass

from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings
from kafkaf.core.skills import store as skills_store
from kafkaf.core.skills.registry import SKILLS_BY_NAME

MAX_ITERATIONS = 4

_ACTION_RE = re.compile(r"ACTION:\s*(\w+)\s*:\s*(.*)", re.DOTALL)
_FINAL_RE = re.compile(r"FINAL ANSWER:\s*(.*)", re.DOTALL)


@dataclass
class PendingApproval:
    approval_id: int
    skill_name: str
    skill_arg: str


@dataclass
class SkillLoopResult:
    """Exactly one of these two fields is set on return."""

    reply: str | None = None
    pending_approval: PendingApproval | None = None


def _skills_preamble() -> str:
    lines = ["You can use tools to help answer the question. Available tools:"]
    for skill in SKILLS_BY_NAME.values():
        lines.append(f"- {skill.name}: {skill.description}")
    lines.append(
        "\nTo use a tool, respond with EXACTLY one line: ACTION: <tool_name>: <argument>\n"
        "You will then be given the result as an OBSERVATION and can act again.\n"
        "When you have enough information, respond with: FINAL ANSWER: <your answer>\n"
        "Never fabricate a tool result — always wait for the real OBSERVATION."
    )
    return "\n".join(lines)


async def run_skill_loop(
    brain: Brain,
    messages: list[dict[str, str]],
    *,
    session_id: str = "",
    user_message: str = "",
    brain_spec: str | None = None,
    allow_pause: bool = True,
) -> SkillLoopResult:
    """Fresh start of the loop. session_id/user_message should be real
    values whenever allow_pause=True (the interactive /chat path) — they're
    only read if the loop actually pauses, to build the approval row.
    Council mode calls this with allow_pause=False (see core/council.py)
    and can leave them at their defaults."""
    conversation = list(messages)
    if conversation and conversation[0]["role"] == "system":
        conversation[0] = {
            "role": "system",
            "content": conversation[0]["content"] + "\n\n" + _skills_preamble(),
        }
    else:
        conversation.insert(0, {"role": "system", "content": _skills_preamble()})

    return await _run_iterations(
        brain,
        conversation,
        0,
        session_id=session_id,
        user_message=user_message,
        brain_spec=brain_spec,
        allow_pause=allow_pause,
    )


async def resume_skill_loop(
    brain: Brain,
    conversation: list[dict[str, str]],
    iterations_used: int,
    *,
    session_id: str,
    user_message: str,
    brain_spec: str | None,
) -> SkillLoopResult:
    """Continue after a human decision has already been applied — the
    caller (core/council.py's resume_chat) has already appended the
    OBSERVATION turn for the approve/deny outcome onto `conversation`.
    iterations_used carries over from the paused call so MAX_ITERATIONS is
    enforced cumulatively across resumes, not reset each time."""
    return await _run_iterations(
        brain,
        conversation,
        iterations_used,
        session_id=session_id,
        user_message=user_message,
        brain_spec=brain_spec,
        allow_pause=True,
    )


async def _run_iterations(
    brain: Brain,
    conversation: list[dict[str, str]],
    iterations_used: int,
    *,
    session_id: str,
    user_message: str,
    brain_spec: str | None,
    allow_pause: bool,
) -> SkillLoopResult:
    """The one loop body shared by a fresh start and every resume depth."""
    for i in range(iterations_used, MAX_ITERATIONS):
        reply = await brain.generate(conversation)

        final_match = _FINAL_RE.search(reply)
        if final_match:
            return SkillLoopResult(reply=final_match.group(1).strip())

        action_match = _ACTION_RE.search(reply)
        if not action_match:
            return SkillLoopResult(reply=reply)  # no tool call requested — treat as final

        skill_name, skill_arg = action_match.group(1), action_match.group(2).strip()
        skill = SKILLS_BY_NAME.get(skill_name)
        start = time.monotonic()

        if skill is None:
            observation = f"error: unknown tool {skill_name!r}"
            audit_store.log_event("skill_error", skill_name, observation)
        elif not skill.read_only and settings.write_skills_mode == "manual":
            # Checked before the requires_approval branch: 'manual' mode
            # blocks every write-capable skill outright, including these
            # two, with no approval prompt shown at all — consistent with
            # how 'manual' already behaves for every other write skill.
            observation = (
                f"error: {skill_name!r} can modify data, and write-capable skills are "
                "set to 'manual' mode — not executed. Switch write-skill mode to "
                "'assisted' or 'autonomous' to allow it."
            )
            audit_store.log_event("skill_write_blocked", skill_name, f"arg={skill_arg[:100]!r}")
        elif skill.requires_approval:
            if not allow_pause:
                # Council mode: pausing N parallel brains for one approval
                # isn't supported in v1 — auto-deny with a clear reason
                # instead of hanging the whole council call.
                observation = (
                    f"error: {skill_name!r} requires human approval, which council mode "
                    "doesn't support (multiple brains can't pause in parallel for one "
                    "approval). Use single-brain mode (council=false) to use this tool."
                )
                audit_store.log_event(
                    "skill_write_blocked", skill_name, f"council auto-denied; arg={skill_arg[:100]!r}"
                )
            else:
                pending_conversation = conversation + [{"role": "assistant", "content": reply}]
                approval_id = skills_store.add_approval(
                    session_id,
                    user_message,
                    brain_spec,
                    skill_name,
                    skill_arg,
                    json.dumps(pending_conversation),
                    i + 1,
                )
                audit_store.log_event(
                    "skill_pending_approval", skill_name, f"arg={skill_arg[:100]!r} -> approval #{approval_id}"
                )
                return SkillLoopResult(
                    pending_approval=PendingApproval(approval_id, skill_name, skill_arg)
                )
        else:
            try:
                observation = await skill.run(skill_arg)
                duration_ms = int((time.monotonic() - start) * 1000)
                # Flagged as a distinct event type in 'assisted' mode so
                # write activity is easy to review after the fact —
                # visibility without blocking.
                event_type = (
                    "skill_write"
                    if not skill.read_only and settings.write_skills_mode == "assisted"
                    else "skill"
                )
                audit_store.log_event(
                    event_type, skill_name, f"arg={skill_arg[:100]!r} -> {observation[:100]!r}", duration_ms
                )
            except Exception as exc:  # a broken skill must not crash the conversation
                observation = f"error: {exc}"
                duration_ms = int((time.monotonic() - start) * 1000)
                audit_store.log_event(
                    "skill_error", skill_name, f"arg={skill_arg[:100]!r} -> {exc}", duration_ms
                )

        conversation.append({"role": "assistant", "content": reply})
        conversation.append({"role": "user", "content": f"OBSERVATION: {observation}"})

    return SkillLoopResult(
        reply="I wasn't able to finish using tools within the allowed steps. Please try rephrasing your question."
    )
