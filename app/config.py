from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lead Automation API"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://leadgen:leadgen@localhost:5432/leadgen"
    n8n_webhook_url: str = "http://localhost:5678/webhook/lead-intake"
    n8n_webhook_timeout_seconds: float = Field(default=5.0, gt=0)
    n8n_webhook_max_attempts: int = Field(default=3, ge=1, le=10)
    n8n_webhook_backoff_seconds: float = Field(default=0.5, ge=0)
    automation_internal_key: str = "replace-this-local-automation-key"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"
    ollama_timeout_seconds: float = Field(default=30.0, gt=0)
    typesafe_api_key: str | None = None
    typesafe_api_url: str = "https://api.typesafe.ai/v1/systemone"
    jev_model: str = "jev-1.13.0"
    jev_timeout_seconds: float = Field(default=15.0, gt=0)
    decision_confidence_threshold: float = Field(default=0.65, ge=0, le=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
