from kafkaf.core.personas.coach import COACH_PERSONA
from kafkaf.core.personas.models import Persona
from kafkaf.core.personas.researcher import RESEARCHER_PERSONA

DEFAULT_PERSONA = Persona(
    key="default",
    name="Kaf",
    system_prompt=(
        "You are Kaf, the default assistant persona of KafKaf (כףכף) — "
        "a free, private, self-hosted AI platform. Be helpful, direct, and honest "
        "about your own limits."
    ),
)

PERSONAS = {
    DEFAULT_PERSONA.key: DEFAULT_PERSONA,
    RESEARCHER_PERSONA.key: RESEARCHER_PERSONA,
    COACH_PERSONA.key: COACH_PERSONA,
}


def get_persona(key: str) -> Persona:
    return PERSONAS.get(key, DEFAULT_PERSONA)
