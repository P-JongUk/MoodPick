"""
ai/tools/embedding_service.py

OpenAI text-embedding-3-small API를 이용한 임베딩 생성 및 캐싱 도구.

- embed_text: 단일 텍스트 임베딩
- get_or_compute_content_embedding: DB 캐시 우선 조회, miss 시 계산 후 저장
- batch_embed_contents: 복수 후보 일괄 임베딩 (캐시 활용)
"""
from openai import AsyncOpenAI
from supabase import create_client, Client
from ai.config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY


_MODEL = "text-embedding-3-small"

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
        # PostgreSQL vector 타입으로 반환된 문자열 형태를 list로 변환
        emb_str = result.data[0]["embedding"]
        if isinstance(emb_str, str):
            import ast
            try:
                return ast.literal_eval(emb_str)
            except:
                pass
        return emb_str

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
        print(f"Failed to cache embedding for {content_id}: {e}")

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
    
    cache = {}
    for row in results.data:
        emb = row["embedding"]
        if isinstance(emb, str):
            import ast
            try:
                emb = ast.literal_eval(emb)
            except:
                pass
        cache[row["content_id"]] = emb
        
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
