from pydantic import BaseModel
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.supabase_service import get_supabase_client
from supabase import Client
from datetime import datetime


router = APIRouter(prefix="/content", tags=["content"])


class ContentFeedbackRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str
    content_id: str
    feedback: str  # "like" or "dislike"


class WatchedContentRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    content_id: str
    content_title: str
    thumbnail_url: Optional[str] = None


class ContentFeedbackResponse(BaseModel):
    id: str
    session_id: Optional[str]
    user_id: str
    content_id: str
    feedback: str
    created_at: str


class WatchedContentResponse(BaseModel):
    id: str
    user_id: str
    session_id: Optional[str]
    content_id: str
    content_title: str
    thumbnail_url: Optional[str]
    watched_at: str


@router.post("/feedback")
async def submit_content_feedback(
    payload: ContentFeedbackRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """콘텐츠 피드백 저장 (👍/👎)"""
    try:
        # feedback 값 검증
        if payload.feedback not in ["like", "dislike"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="feedback must be 'like' or 'dislike'"
            )

        result = supabase.table("content_feedback").insert({
            "session_id": payload.session_id,
            "user_id": payload.user_id,
            "content_id": payload.content_id,
            "feedback": payload.feedback,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()

        if result.data and len(result.data) > 0:
            feedback = result.data[0]
            return ContentFeedbackResponse(**feedback)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save feedback"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/watched")
async def record_watched_content(
    payload: WatchedContentRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """시청한 콘텐츠 기록"""
    try:
        result = supabase.table("watched_content_records").insert({
            "user_id": payload.user_id,
            "session_id": payload.session_id,
            "content_id": payload.content_id,
            "content_title": payload.content_title,
            "thumbnail_url": payload.thumbnail_url,
            "watched_at": datetime.utcnow().isoformat(),
        }).execute()

        if result.data and len(result.data) > 0:
            content = result.data[0]
            return WatchedContentResponse(**content)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record watched content"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/history/{user_id}", response_model=List[WatchedContentResponse])
async def get_content_history(
    user_id: str,
    limit: int = 20,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자가 시청한 콘텐츠 기록 (최근 20개)"""
    try:
        result = supabase.table("watched_content_records").select("*").eq(
            "user_id", user_id
        ).order("watched_at", desc=True).limit(limit).execute()

        if result.data:
            return [WatchedContentResponse(**item) for item in result.data]
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/feedback/{user_id}")
async def get_feedback_summary(
    user_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자의 피드백 통계 (좋아요/싫어요 카운트)"""
    try:
        result = supabase.table("content_feedback").select("*").eq(
            "user_id", user_id
        ).execute()

        if not result.data:
            return {"likes": 0, "dislikes": 0}

        likes = len([r for r in result.data if r["feedback"] == "like"])
        dislikes = len([r for r in result.data if r["feedback"] == "dislike"])

        return {
            "user_id": user_id,
            "likes": likes,
            "dislikes": dislikes,
            "total": likes + dislikes
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
