from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKAF_")

    # A single, legible dial instead of scattered feature flags — see
    # kafkaf/core/autonomy.py for what each tier unlocks.
    autonomy_level: Literal["observe", "assisted", "autonomous"] = "autonomous"

    # A second, independent dial: autonomy_level gates whether skills run
    # at all; this gates the write-capable subset specifically (files,
    # journal, identity, reminders, schedule — see Skill.read_only) once
    # skills are already allowed. "manual" blocks them outright (no
    # pause-and-resume confirmation flow exists yet — see
    # core/skills/loop.py); "assisted" runs them but audit-logs them under
    # a distinct event type for easy review; "autonomous" is today's
    # unchanged default.
    write_skills_mode: Literal["manual", "assisted", "autonomous"] = "autonomous"

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

    # Sandboxed directory the "files" and "document_search" skills are confined to.
    skills_workspace_dir: str = "workspace"

    # Requests/minute per client IP before non-exempt routes start returning
    # 429. Generous default — single-user platform, not a public API. 0
    # disables rate limiting entirely.
    rate_limit_per_minute: int = 120


settings = Settings()
