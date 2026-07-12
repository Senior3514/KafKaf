from kafkaf.core.personas.models import Persona

DEFAULT_PERSONA = Persona(
    key="default",
    name="Kaf",
    system_prompt=(
        "You are Kaf, the default assistant persona of KafKaf (כףכף) — "
        "a free, private, self-hosted AI platform. Be helpful, direct, and honest "
        "about your own limits."
    ),
)

PERSONAS = {DEFAULT_PERSONA.key: DEFAULT_PERSONA}


def get_persona(key: str) -> Persona:
    return PERSONAS.get(key, DEFAULT_PERSONA)
