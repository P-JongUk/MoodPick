"""
ai/tools/rag_search.py

RAG vector search tool for the Counselor Agent.
Mirrors the logic in backend/app/routers/rag.py without importing from it.
"""

from openai import OpenAI
from supabase import create_client, Client

from ai.config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# ── Constants (must match backend config) ─────────────────────────────────────
_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMENSIONS = 1536


def _get_openai() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env.local")
    return OpenAI(api_key=OPENAI_API_KEY)


def _get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def search_rag_context(
    query_text: str,
    top_k: int = 5,
    user_id: str | None = None,
) -> list[dict]:
    """
    Search the RAG knowledge base for chunks relevant to the query.

    Args:
        query_text: The user's message or a derived search query.
        top_k:      Number of chunks to return.
        user_id:    Optional — narrows search to user-specific documents.

    Returns:
        List of dicts: [{"content": "...", "similarity": 0.87, "chunk_id": "..."}, ...]
    """
    if not query_text or not query_text.strip():
        return []

    # 1. Create embedding
    openai_client = _get_openai()
    response = openai_client.embeddings.create(
        model=_EMBEDDING_MODEL,
        input=query_text.strip(),
    )
    embedding: list[float] = response.data[0].embedding

    if len(embedding) != _EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"Unexpected embedding dimension: {len(embedding)} != {_EMBEDDING_DIMENSIONS}"
        )

    # 2. Call Supabase RPC
    supabase = _get_supabase()
    result = supabase.rpc(
        "match_rag_chunks",
        {
            "query_embedding": embedding,
            "match_count": top_k,
            "filter_user_id": user_id,
        },
    ).execute()

    rows = result.data or []
    return [
        {
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "similarity": float(row["similarity"]),
        }
        for row in rows
    ]
