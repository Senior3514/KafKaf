import pytest

from kafkaf.core import autonomy


def test_skills_allowed_for_assisted_and_autonomous():
    assert autonomy.skills_allowed("assisted") is True
    assert autonomy.skills_allowed("autonomous") is True


def test_skills_not_allowed_for_observe():
    assert autonomy.skills_allowed("observe") is False


def test_autopilot_default_on_only_for_autonomous():
    assert autonomy.autopilot_default_on("autonomous") is True
    assert autonomy.autopilot_default_on("assisted") is False
    assert autonomy.autopilot_default_on("observe") is False


def test_defaults_to_configured_settings_level(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.autonomy_level", "observe")
    assert autonomy.skills_allowed() is False
    assert autonomy.autopilot_default_on() is False


def test_every_tier_has_a_description():
    for tier in autonomy.TIERS:
        assert tier in autonomy.DESCRIPTIONS


def test_invalid_autonomy_level_rejected():
    from kafkaf.core.config import Settings

    with pytest.raises(Exception):
        Settings(autonomy_level="godmode")
