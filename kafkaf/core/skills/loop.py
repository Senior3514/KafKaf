"""A brain-agnostic tool-use loop — the ReAct pattern (Yao et al. 2022,
"ReAct: Synergizing Reasoning and Acting in Language Models," arXiv:2210.03629).

Deliberately text-protocol based rather than provider-specific function-
calling APIs: every Brain's generate() only ever sees/returns plain text
messages, so skills work uniformly across Ollama, every API brain, and
(once it's capable enough) the small owned model too — no per-provider
special-casing of the Brain interface required.
"""

import re
import time

from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings
from kafkaf.core.skills.registry import SKILLS_BY_NAME

MAX_ITERATIONS = 4

_ACTION_RE = re.compile(r"ACTION:\s*(\w+)\s*:\s*(.*)", re.DOTALL)
_FINAL_RE = re.compile(r"FINAL ANSWER:\s*(.*)", re.DOTALL)


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


async def run_skill_loop(brain: Brain, messages: list[dict[str, str]]) -> str:
    conversation = list(messages)
    if conversation and conversation[0]["role"] == "system":
        conversation[0] = {
            "role": "system",
            "content": conversation[0]["content"] + "\n\n" + _skills_preamble(),
        }
    else:
        conversation.insert(0, {"role": "system", "content": _skills_preamble()})

    for _ in range(MAX_ITERATIONS):
        reply = await brain.generate(conversation)

        final_match = _FINAL_RE.search(reply)
        if final_match:
            return final_match.group(1).strip()

        action_match = _ACTION_RE.search(reply)
        if not action_match:
            return reply  # no tool call requested — treat as the final answer

        skill_name, skill_arg = action_match.group(1), action_match.group(2).strip()
        skill = SKILLS_BY_NAME.get(skill_name)
        start = time.monotonic()
        if skill is None:
            observation = f"error: unknown tool {skill_name!r}"
            audit_store.log_event("skill_error", skill_name, observation)
        elif not skill.read_only and settings.write_skills_mode == "manual":
            # A second, independent dial from autonomy_level (which already
            # allowed skills to run at all) — this gates the write-capable
            # subset specifically. No pause-and-resume confirmation flow
            # exists for a synchronous /chat call, so "manual" honestly
            # means "off until you switch modes," same as the other
            # autonomy-style dials already in this product.
            observation = (
                f"error: {skill_name!r} can modify data, and write-capable skills are "
                "set to 'manual' mode — not executed. Switch write-skill mode to "
                "'assisted' or 'autonomous' to allow it."
            )
            audit_store.log_event("skill_write_blocked", skill_name, f"arg={skill_arg[:100]!r}")
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

    return "I wasn't able to finish using tools within the allowed steps. Please try rephrasing your question."
