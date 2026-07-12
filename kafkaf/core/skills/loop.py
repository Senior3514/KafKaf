"""A brain-agnostic tool-use loop — the ReAct pattern (Yao et al. 2022,
"ReAct: Synergizing Reasoning and Acting in Language Models," arXiv:2210.03629).

Deliberately text-protocol based rather than provider-specific function-
calling APIs: every Brain's generate() only ever sees/returns plain text
messages, so skills work uniformly across Ollama, every API brain, and
(once it's capable enough) the small owned model too — no per-provider
special-casing of the Brain interface required.
"""

import re

from kafkaf.core.brains.base import Brain
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
        if skill is None:
            observation = f"error: unknown tool {skill_name!r}"
        else:
            try:
                observation = await skill.run(skill_arg)
            except Exception as exc:  # a broken skill must not crash the conversation
                observation = f"error: {exc}"

        conversation.append({"role": "assistant", "content": reply})
        conversation.append({"role": "user", "content": f"OBSERVATION: {observation}"})

    return "I wasn't able to finish using tools within the allowed steps. Please try rephrasing your question."
