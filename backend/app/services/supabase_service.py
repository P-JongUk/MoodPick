from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError(
            "Supabase 환경 변수가 없습니다. backend/.env.local에 SUPABASE_URL과 SUPABASE_KEY를 설정해 주세요."
        )

    return create_client(settings.supabase_url, settings.supabase_key)
