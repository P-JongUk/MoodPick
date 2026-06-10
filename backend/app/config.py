from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    openai_api_key: str | None = None
    rag_embedding_model: str = "text-embedding-3-small"
    rag_embedding_dimensions: int = 1536
    youtube_api_key: str | None = None
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000"
    reminder_feature_enabled: bool = False
    reminder_scheduler_enabled: bool = False
    reminder_scheduler_interval_seconds: int = 300
    admin_user_ids: str = ""
    admin_emails: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "development", "dev", "true", "1", "yes", "on"}:
                return True
        return value

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cors_origins() -> list[str]:
    settings = get_settings()
    raw = settings.cors_origins.strip()
    if not raw:
        return []
    if raw == "*":
        if settings.environment.lower() not in {"development", "local", "test"}:
            raise ValueError("CORS_ORIGINS='*' is not allowed outside local development")
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
