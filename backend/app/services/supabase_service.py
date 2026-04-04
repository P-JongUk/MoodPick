from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    effective_key = settings.supabase_service_role_key or settings.supabase_key

    if not settings.supabase_url or not effective_key:
        raise RuntimeError(
            "Supabase 환경 변수가 없습니다. backend/.env.local에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY(권장) 또는 SUPABASE_KEY를 설정해 주세요."
        )

    return create_client(settings.supabase_url, effective_key)
