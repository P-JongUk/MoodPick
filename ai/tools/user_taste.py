"""
ai/tools/user_taste.py

사용자의 좋아요 이력을 기반으로 취향 벡터를 관리하는 도구.

- get_user_taste_vector: DB에 저장된 유저 벡터 조회
- compute_user_taste_vector: 좋아요 이력으로 새로운 벡터 계산 (시간 가중치 적용)
- refresh_user_taste_vector: 벡터 갱신 및 DB 저장
- get_onboarding_vector: 콜드스타트 유저를 위한 온보딩 기반 임시 벡터 생성
"""
import ast
import logging
from datetime import datetime, timezone

import numpy as np
from supabase import create_client, Client
from ai.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from ai.tools.embedding_service import get_or_compute_content_embedding, embed_text
from ai.tools.user_profile import get_user_profile

logger = logging.getLogger(__name__)

MIN_LIKES_FOR_VECTOR = 3
HALF_LIFE_DAYS = 90

def _get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

async def get_user_taste_vector(user_id: str) -> dict | None:
    """user_taste_vectors 테이블에서 조회."""
    supabase = _get_supabase()
    result = supabase.table("user_taste_vectors").select("*").eq("user_id", user_id).execute()

    if not result.data:
        return None

    row = result.data[0]
    emb = row.get("embedding")
    if isinstance(emb, str):
        try:
            row["embedding"] = ast.literal_eval(emb)
        except (ValueError, SyntaxError) as e:
            logger.warning(
                "Failed to parse user_taste_vector embedding for user_id=%s: %s",
                user_id,
                e,
            )
            row["embedding"] = None
    return row

async def compute_user_taste_vector(user_id: str) -> tuple[list[float], int] | None:
    """좋아요 영상들로 시간 가중 평균 계산. None이면 콜드스타트."""
    supabase = _get_supabase()

    # 1. 좋아요 이력 가져오기
    liked_result = supabase.table("content_feedback") \
        .select("content_id, created_at") \
        .eq("user_id", user_id).eq("feedback", "like") \
        .execute()
    liked = liked_result.data or []

    if len(liked) < MIN_LIKES_FOR_VECTOR:
        return None

    embeddings = []
    weights = []
    now = datetime.now(timezone.utc)

    # 2. 임베딩 조회 및 가중치 적용
    for row in liked:
        # 캐시가 있는 경우에만 가져오고, 없으면 일단 스킵 (비동기 병목 방지 위해)
        emb = await get_or_compute_content_embedding(row["content_id"])
        if emb is None:
            continue

        # created_at이 naive인 경우 UTC로 간주해 tz 정보 보존.
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - created_at).days)
        weight = 0.5 ** (age_days / HALF_LIFE_DAYS)
        embeddings.append(emb)
        weights.append(weight)
        
    if not embeddings:
        return None
        
    # 가중 평균 + L2 정규화
    weighted = np.average(embeddings, axis=0, weights=weights)
    normalized = weighted / np.linalg.norm(weighted)
    return normalized.tolist(), len(embeddings)

async def refresh_user_taste_vector(user_id: str) -> None:
    """compute -> upsert. 좋아요 이벤트에서 백그라운드로 호출."""
    vector_data = await compute_user_taste_vector(user_id)
    if not vector_data:
        return
        
    vector, count = vector_data
    supabase = _get_supabase()
    
    try:
        supabase.table("user_taste_vectors").upsert({
            "user_id": user_id,
            "embedding": vector,
            "embedding_model": "text-embedding-3-small",
            "source_count": count,
            "strategy": "time_weighted_avg",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        logger.warning("Failed to refresh user_taste_vector for %s: %s", user_id, e)

async def get_onboarding_vector(user_id: str) -> list[float] | None:
    """콜드스타트 폴백: 온보딩 정보 임베딩."""
    profile = get_user_profile(user_id)
    if not profile:
        return None
        
    concerns = ", ".join(profile.get("concerns", []))
    comfort_style = ", ".join(profile.get("comfort_style", []))
    
    if not concerns and not comfort_style:
        return None
        
    source_text = f"고민: {concerns}. 위로 방식 선호: {comfort_style}"
    return await embed_text(source_text)
