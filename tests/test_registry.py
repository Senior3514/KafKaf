import sys

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


def test_registry_and_api_import_without_torch_installed():
    """The base backend must start and serve every non-"own" brain without
    torch installed (it's an optional [train] extra) — a real bug where
    registry.py imported OwnModelBrain (and therefore torch) at module
    level, breaking `kafkaf-server` for anyone who only ran `pip install
    -e ".[dev]"`, surfaced via live testing on a fresh machine."""
    modules_to_purge = [
        name
        for name in sys.modules
        if name == "torch" or name.startswith(("torch.", "kafkaf.model", "kafkaf.core.brains.own_model_brain"))
    ]
    saved = {name: sys.modules[name] for name in modules_to_purge}
    also_purge_for_reimport = ["kafkaf.core.brains.registry", "kafkaf.core.api", "kafkaf.core.council"]
    saved.update({name: sys.modules[name] for name in also_purge_for_reimport if name in sys.modules})

    for name in list(saved):
        del sys.modules[name]
    sys.modules["torch"] = None  # any `import torch` now raises ImportError

    try:
        import importlib

        registry = importlib.import_module("kafkaf.core.brains.registry")
        assert isinstance(registry.get_brain("ollama:llama3"), OllamaBrain)

        with pytest.raises(ImportError):
            registry.get_brain("own")

        # The rest of the backend must import cleanly too, not just registry.
        importlib.import_module("kafkaf.core.api")
    finally:
        for name in list(sys.modules):
            if name == "torch" and sys.modules[name] is None:
                del sys.modules[name]
        sys.modules.update(saved)
        importlib.invalidate_caches()
