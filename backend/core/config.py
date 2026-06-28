"""
SELLO Backend — Core Configuration
Reads all settings from environment variables with strong typing.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "SELLO"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    api_version: str = "v1"
    secret_key: str = "change_me_to_a_long_random_secret_key"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://sello:sello_secret@localhost:5432/sello_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://:redis_secret@localhost:6379/0"

    # ── Qdrant ───────────────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_leads: str = "sello_leads"
    qdrant_collection_memory: str = "sello_memory"

    # ── Ollama ───────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "qwen2.5:7b"
    ollama_embedding_model: str = "nomic-embed-text"

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret_key: str = "change_me_jwt_secret_key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # ── CORS ─────────────────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"

    # ── Platform Connectors ──────────────────────────────────────────────────
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "SELLO/1.0"
    twitter_bearer_token: str = ""
    github_token: str = ""
    discord_bot_token: str = ""

    # ── Notifications ────────────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def get_settings() -> Settings:
    """Cached singleton settings instance."""
    return Settings()
