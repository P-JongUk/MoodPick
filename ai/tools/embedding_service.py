"""
ai/tools/embedding_service.py

OpenAI text-embedding-3-small API를 이용한 임베딩 생성 및 캐싱 도구.

- embed_text: 단일 텍스트 임베딩
- get_or_compute_content_embedding: DB 캐시 우선 조회, miss 시 계산 후 저장
- batch_embed_contents: 복수 후보 일괄 임베딩 (캐시 활용)
"""
import ast
import logging

from openai import AsyncOpenAI
from supabase import create_client, Client
from ai.config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY


logger = logging.getLogger(__name__)
_MODEL = "text-embedding-3-small"


def _parse_embedding(raw, content_id: str | None = None) -> list[float] | None:
    """DB가 vector 컬럼을 문자열로 반환하는 경우를 대비해 list[float]로 정규화한다.
    파싱 실패 시 None을 반환해 호출 측이 후보에서 자연스럽게 제외하도록 한다.
    """
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError) as e:
            logger.warning(
                "Failed to parse embedding string for content_id=%s: %s",
                content_id,
                e,
            )
    return None

def _get_openai() -> AsyncOpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return AsyncOpenAI(api_key=OPENAI_API_KEY)

def _get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

async def embed_text(text: str) -> list[float]:
    """OpenAI embedding API 호출"""
    client = _get_openai()
    response = await client.embeddings.create(
        input=text,
        model=_MODEL
    )
    return response.data[0].embedding

async def get_or_compute_content_embedding(
    content_id: str,
    source_text: str | None = None,
    metadata: dict | None = None,
) -> list[float] | None:
    """캐시 우선 조회 -> miss 시 임베딩 후 insert"""
    supabase = _get_supabase()

    # 1. DB에서 캐시 조회
    result = supabase.table("content_embeddings").select("embedding").eq("content_id", content_id).execute()
    if result.data:
        cached = _parse_embedding(result.data[0].get("embedding"), content_id=content_id)
        if cached is not None:
            return cached
        # 파싱 실패 시 cache miss로 간주하고 재계산 흐름으로 빠진다.

    # 2. Cache miss -> 새로 생성
    if not source_text:
        return None

    embedding = await embed_text(source_text)

    # 3. DB에 저장
    try:
        supabase.table("content_embeddings").insert({
            "content_id": content_id,
            "source_text": source_text,
            "embedding": embedding,
            "embedding_model": _MODEL,
            "metadata": metadata or {}
        }).execute()
    except Exception as e:
        logger.warning("Failed to cache embedding for %s: %s", content_id, e)

    return embedding

async def batch_embed_contents(items: list[dict]) -> dict[str, list[float]]:
    """
    여러 후보(items)를 병렬 임베딩 (캐시 활용).
    items는 {"content_id": "...", "title": "...", "description": "..."} 형태의 리스트라고 가정.
    """
    supabase = _get_supabase()
    content_ids = [item["content_id"] for item in items if "content_id" in item]
    
    # DB에서 일괄 조회
    results = supabase.table("content_embeddings").select("content_id, embedding").in_("content_id", content_ids).execute()

    cache: dict[str, list[float]] = {}
    for row in (results.data or []):
        cid = row.get("content_id")
        emb = _parse_embedding(row.get("embedding"), content_id=cid)
        if cid and emb is not None:
            cache[cid] = emb
        
    # 캐시 없는 아이템 임베딩
    embeddings_map = {}
    for item in items:
        cid = item.get("content_id")
        if not cid: continue
            
        if cid in cache:
            embeddings_map[cid] = cache[cid]
        else:
            text = f"{item.get('title', '')} {item.get('description', '')}".strip()
            if text:
                emb = await get_or_compute_content_embedding(cid, source_text=text, metadata=item)
                if emb:
                    embeddings_map[cid] = emb
                    
    return embeddings_map
