from app.config import Settings, get_settings
from app.services.supabase_service import get_supabase_client


def get_application_settings() -> Settings:
    return get_settings()


def get_supabase_dependency():
    return get_supabase_client()
