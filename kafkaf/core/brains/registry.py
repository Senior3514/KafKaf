from kafkaf.core.brains.anthropic_brain import AnthropicBrain
from kafkaf.core.brains.base import Brain
from kafkaf.core.brains.gemini_brain import GeminiBrain
from kafkaf.core.brains.ollama_brain import OllamaBrain
from kafkaf.core.brains.openai_brain import OpenAIBrain
from kafkaf.core.brains.own_model_brain import OwnModelBrain

_PROVIDERS = {
    "ollama": OllamaBrain,
    "openai": OpenAIBrain,
    "anthropic": AnthropicBrain,
    "gemini": GeminiBrain,
}


def get_brain(spec: str) -> Brain:
    """Resolve a teacher spec string into a Brain instance.

    Examples: "ollama:llama3", "openai:gpt-4o-mini", "anthropic:claude-3-5-haiku-latest",
    "gemini:gemini-1.5-flash", or "own" for KafKaf's own trained model.
    """
    if spec == "own":
        return OwnModelBrain()

    if ":" not in spec:
        raise ValueError(
            f"Invalid brain spec {spec!r} — expected 'provider:model' "
            "(e.g. 'ollama:llama3') or 'own'."
        )

    provider, model = spec.split(":", 1)
    provider_cls = _PROVIDERS.get(provider)
    if provider_cls is None:
        raise ValueError(
            f"Unknown provider {provider!r}. Known providers: {sorted(_PROVIDERS)}, or 'own'."
        )

    return provider_cls(model=model)
