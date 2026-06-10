from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.auth import CurrentUser, get_current_user, require_same_user
from app.config import get_settings
from app.services.embedding_service import create_text_embedding
from app.services.supabase_service import get_supabase_client


router = APIRouter(prefix="/rag", tags=["rag"])


class RagSearchRequest(BaseModel):
    query_embedding: List[float] = Field(..., description="1536-dim embedding vector")
    user_id: Optional[str] = Field(default=None, description="Optional user scope")
    top_k: int = Field(default=5, ge=1, le=20)


class RagSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    similarity: float


class RagSearchByTextRequest(BaseModel):
    query_text: str = Field(..., min_length=1)
    user_id: Optional[str] = Field(default=None)
    top_k: int = Field(default=5, ge=1, le=20)


def _run_similarity_search(
    supabase: Client,
    query_embedding: List[float],
    top_k: int,
    user_id: str,
) -> List[RagSearchResult]:
    rpc_payload: dict[str, Any] = {
        "query_embedding": query_embedding,
        "match_count": top_k,
        "filter_user_id": user_id,
    }
    result = supabase.rpc("match_rag_chunks", rpc_payload).execute()

    rows = result.data or []
    return [
        RagSearchResult(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            content=row["content"],
            similarity=float(row["similarity"]),
        )
        for row in rows
    ]


@router.get("/health")
async def rag_health(supabase: Client = Depends(get_supabase_client)):
    """RAG 테이블 접근 가능 여부를 확인합니다."""
    try:
        result = supabase.table("rag_chunks").select("id", count="exact").limit(1).execute()
        count = result.count if result.count is not None else 0
        return {"status": "ok", "rag_chunks_count": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG health check failed",
        )


@router.post("/search", response_model=List[RagSearchResult])
async def rag_search(
    payload: RagSearchRequest,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    """입력 임베딩으로 유사한 RAG 청크를 검색합니다."""
    settings = get_settings()
    if payload.user_id is not None:
        require_same_user(payload.user_id, current_user)
    if len(payload.query_embedding) != settings.rag_embedding_dimensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"query_embedding must have exactly {settings.rag_embedding_dimensions} dimensions",
        )

    try:
        return _run_similarity_search(
            supabase=supabase,
            query_embedding=payload.query_embedding,
            top_k=payload.top_k,
            user_id=current_user.id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG search failed",
        )


@router.post("/search-by-text", response_model=List[RagSearchResult])
async def rag_search_by_text(
    payload: RagSearchByTextRequest,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    """입력 텍스트를 임베딩으로 변환한 뒤 유사한 RAG 청크를 검색합니다."""
    try:
        if payload.user_id is not None:
            require_same_user(payload.user_id, current_user)
        query_embedding = create_text_embedding(payload.query_text)
        return _run_similarity_search(
            supabase=supabase,
            query_embedding=query_embedding,
            top_k=payload.top_k,
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query_text must not be empty",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG search-by-text failed",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG search-by-text failed",
        )
