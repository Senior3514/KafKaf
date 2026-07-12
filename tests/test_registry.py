import pytest

from kafkaf.core.brains.anthropic_brain import AnthropicBrain
from kafkaf.core.brains.gemini_brain import GeminiBrain
from kafkaf.core.brains.ollama_brain import OllamaBrain
from kafkaf.core.brains.openai_brain import OpenAIBrain
from kafkaf.core.brains.own_model_brain import OwnModelBrain
from kafkaf.core.brains.registry import get_brain


def test_get_brain_own():
    assert isinstance(get_brain("own"), OwnModelBrain)


def test_get_brain_ollama():
    brain = get_brain("ollama:llama3")
    assert isinstance(brain, OllamaBrain)
    assert brain.name == "llama3"


def test_get_brain_openai(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.openai_api_key", "test-key")
    brain = get_brain("openai:gpt-4o-mini")
    assert isinstance(brain, OpenAIBrain)
    assert brain.name == "gpt-4o-mini"


def test_get_brain_openai_missing_key(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.openai_api_key", None)
    with pytest.raises(RuntimeError):
        get_brain("openai:gpt-4o-mini")


def test_get_brain_anthropic(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.anthropic_api_key", "test-key")
    assert isinstance(get_brain("anthropic:claude-3-5-haiku-latest"), AnthropicBrain)


def test_get_brain_gemini(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.gemini_api_key", "test-key")
    assert isinstance(get_brain("gemini:gemini-1.5-flash"), GeminiBrain)


def test_get_brain_unknown_provider():
    with pytest.raises(ValueError):
        get_brain("bogus:model")


def test_get_brain_invalid_spec():
    with pytest.raises(ValueError):
        get_brain("no-colon-here")
