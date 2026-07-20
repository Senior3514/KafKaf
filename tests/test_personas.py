from kafkaf.core.personas.default import DEFAULT_PERSONA, PERSONAS, get_persona
from kafkaf.core.personas.style import VOICE_STYLE


def test_default_persona_is_kaf():
    assert DEFAULT_PERSONA.key == "default"
    assert get_persona("default") is DEFAULT_PERSONA


def test_unknown_persona_falls_back_to_default():
    assert get_persona("nonexistent") is DEFAULT_PERSONA


def test_researcher_and_coach_personas_exist_and_are_distinct():
    researcher = get_persona("researcher")
    coach = get_persona("coach")
    assert researcher.key == "researcher"
    assert coach.key == "coach"
    assert researcher.system_prompt != coach.system_prompt
    assert researcher.system_prompt != DEFAULT_PERSONA.system_prompt


def test_every_persona_has_a_nonempty_system_prompt():
    for persona in PERSONAS.values():
        assert persona.system_prompt.strip()
        assert persona.name.strip()


def test_every_persona_includes_shared_voice_style_exactly_once():
    for persona in PERSONAS.values():
        assert persona.system_prompt.count(VOICE_STYLE) == 1
