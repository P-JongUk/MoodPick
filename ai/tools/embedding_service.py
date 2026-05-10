"""
ai/tools/embedding_service.py

OpenAI text-embedding-3-small API를 이용한 임베딩 생성 및 캐싱 도구.

- embed_text: 단일 텍스트 임베딩
- get_or_compute_content_embedding: DB 캐시 우선 조회, miss 시 계산 후 저장
- batch_embed_contents: 복수 후보 일괄 임베딩 (캐시 활용)
"""
import ast
import asyncio
import logging

from openai import AsyncOpenAI
from supabase import create_client, Client
from ai.config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY


logger = logging.getLogger(__name__)
_MODEL = "text-embedding-3-small"
_EMBED_SEMAPHORE = asyncio.Semaphore(5)


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

def _select_cached_embedding(content_id: str) -> list[float] | None:
    supabase = _get_supabase()
    result = supabase.table("content_embeddings").select("embedding").eq("content_id", content_id).execute()
    if not result.data:
        return None
    return _parse_embedding(result.data[0].get("embedding"), content_id=content_id)


def _insert_content_embedding(content_id: str, source_text: str, embedding: list[float], metadata: dict | None) -> None:
    supabase = _get_supabase()
    supabase.table("content_embeddings").insert({
        "content_id": content_id,
        "source_text": source_text,
        "embedding": embedding,
        "embedding_model": _MODEL,
        "metadata": metadata or {},
    }).execute()


async def get_or_compute_content_embedding(
    content_id: str,
    source_text: str | None = None,
    metadata: dict | None = None,
) -> list[float] | None:
    """캐시 우선 조회 -> miss 시 임베딩 후 insert (단건 진입점)."""
    cached = await asyncio.to_thread(_select_cached_embedding, content_id)
    if cached is not None:
        return cached

    if not source_text:
        return None

    embedding = await embed_text(source_text)

    try:
        await asyncio.to_thread(_insert_content_embedding, content_id, source_text, embedding, metadata)
    except Exception as e:
        logger.warning("Failed to cache embedding for %s: %s", content_id, e)

    return embedding

def _select_cached_embeddings_bulk(content_ids: list[str]) -> dict[str, list[float]]:
    supabase = _get_supabase()
    results = supabase.table("content_embeddings").select("content_id, embedding").in_(
        "content_id", content_ids
    ).execute()
    cache: dict[str, list[float]] = {}
    for row in (results.data or []):
        cid = row.get("content_id")
        emb = _parse_embedding(row.get("embedding"), content_id=cid)
        if cid and emb is not None:
            cache[cid] = emb
    return cache


async def _embed_and_cache_miss(
    cid: str, source_text: str, metadata: dict
) -> tuple[str, list[float] | None]:
    """캐시 미스 후보 전용: 캐시 재조회 건너뛰고 embed + insert만."""
    async with _EMBED_SEMAPHORE:
        embedding = await embed_text(source_text)
    try:
        await asyncio.to_thread(_insert_content_embedding, cid, source_text, embedding, metadata)
    except Exception as e:
        logger.warning("Failed to cache embedding for %s: %s", cid, e)
    return cid, embedding


async def batch_embed_contents(items: list[dict]) -> dict[str, list[float]]:
    """
    여러 후보(items)를 병렬 임베딩 (캐시 활용).
    items는 {"content_id": "...", "title": "...", "description": "..."} 형태의 리스트라고 가정.
    """
    content_ids = [item["content_id"] for item in items if "content_id" in item]

    cache = await asyncio.to_thread(_select_cached_embeddings_bulk, content_ids)

    embeddings_map: dict[str, list[float]] = {}
    miss_tasks = []
    for item in items:
        cid = item.get("content_id")
        if not cid:
            continue

        if cid in cache:
            embeddings_map[cid] = cache[cid]
        else:
            text = f"{item.get('title', '')} {item.get('description', '')}".strip()
            if text:
                miss_tasks.append(_embed_and_cache_miss(cid, text, item))

    if miss_tasks:
        results = await asyncio.gather(*miss_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Embedding task failed: %s", result)
                continue
            cid, emb = result
            if emb:
                embeddings_map[cid] = emb

    return embeddings_map
