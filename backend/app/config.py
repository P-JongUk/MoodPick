from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_service_role_key: str | None = None
    openai_api_key: str | None = None
    rag_embedding_model: str = "text-embedding-3-small"
    rag_embedding_dimensions: int = 1536
    youtube_api_key: str | None = None
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    debug: bool = True
    reminder_scheduler_enabled: bool = False
    reminder_scheduler_interval_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
