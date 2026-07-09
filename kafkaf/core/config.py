from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKAF_")

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    db_path: str = "kafkaf.db"
    host: str = "0.0.0.0"
    port: int = 8420


settings = Settings()
