from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKAF_")

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    db_path: str = "kafkaf.db"
    host: str = "0.0.0.0"
    port: int = 8420

    # Our own from-scratch-trained model (see kafkaf/model/ and docs/ROADMAP.md phase 6).
    own_model_checkpoint_path: str = "kafkaf-own-model.pt"
    own_model_preset: str = "tiny"

    # Optional API-model "teachers" for enrichment. Never hardcode these — env vars only.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    # Comma-separated brain specs for council mode, e.g. "ollama:llama3,ollama:qwen3:4b".
    council_brains: str | None = None

    # Sandboxed directory the "files" skill is confined to.
    skills_workspace_dir: str = "workspace"


settings = Settings()
