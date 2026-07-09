"""The single seam where a chat turn is resolved.

Today this routes to one configured brain. The intended growth path (see
docs/ROADMAP.md, phase 3) is to fan a query out to several brains in
parallel and synthesize their answers — an honest "council of brains", not
a single monolithic model.
"""

from kafkaf.core.brains.base import Brain
from kafkaf.core.brains.ollama_brain import OllamaBrain
from kafkaf.core.memory import store
from kafkaf.core.personas.default import get_persona

_default_brain: Brain = OllamaBrain()


async def handle_chat(
    session_id: str,
    message: str,
    persona_key: str = "default",
    brain: Brain | None = None,
) -> str:
    persona = get_persona(persona_key)
    active_brain = brain or _default_brain

    history = store.get_history(session_id)
    messages = [
        {"role": "system", "content": persona.system_prompt},
        *history,
        {"role": "user", "content": message},
    ]

    reply = await active_brain.generate(messages)

    store.save_message(session_id, "user", message)
    store.save_message(session_id, "assistant", reply)
    return reply
