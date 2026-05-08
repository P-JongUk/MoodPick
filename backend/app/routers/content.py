from pydantic import BaseModel
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from app.services.supabase_service import get_supabase_client
from supabase import Client
from datetime import datetime, timezone


router = APIRouter(prefix="/content", tags=["content"])

# 비AI 시드 추천 (YouTube 영상 + Spotify 트랙). 이후 검색 API·개인화로 대체 가능.
_SEED_RECOMMENDATIONS: list[dict] = [
    {
        "id": "seed-rec-yt-lofi",
        "content_id": "youtube:jfKfPfyJRdk",
        "content_title": "잠시 쉬어가는 음악 (데모)",
        "thumbnail_url": "https://img.youtube.com/vi/jfKfPfyJRdk/mqdefault.jpg",
        "media_provider": "youtube",
        "media_url": None,
    },
    {
        "id": "seed-rec-sp-1",
        "content_id": "spotify:track:4iV5W9uYEdYUVa79Axb7Rh",
        "content_title": "클래식 힐링 플레이리스트 샘플",
        "thumbnail_url": None,
        "media_provider": "spotify",
        "media_url": "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh",
    },
    {
        "id": "seed-rec-yt-nature",
        "content_id": "youtube:LnBnm_tZrhg",
        "content_title": "자연 속 휴식 (데모)",
        "thumbnail_url": "https://img.youtube.com/vi/LnBnm_tZrhg/mqdefault.jpg",
        "media_provider": "youtube",
        "media_url": None,
    },
    {
        "id": "seed-rec-sp-2",
        "content_id": "spotify:track:3YMgCpfrgrje64XnIAgYH7",
        "content_title": "잔잔한 재즈 샘플",
        "thumbnail_url": None,
        "media_provider": "spotify",
        "media_url": "https://open.spotify.com/track/3YMgCpfrgrje64XnIAgYH7",
    },
]


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
    media_provider: Optional[Literal["youtube", "spotify"]] = None
    media_url: Optional[str] = None


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
    media_provider: Optional[str] = None
    media_url: Optional[str] = None


class ContentRecommendationItem(BaseModel):
    id: str
    content_id: str
    content_title: str
    thumbnail_url: Optional[str] = None
    media_provider: Optional[str] = None
    media_url: Optional[str] = None
    watched_at: str
    session_id: Optional[str] = None


@router.post("/feedback")
async def submit_content_feedback(
    payload: ContentFeedbackRequest,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client)
):
    """콘텐츠 피드백 저장/변경 (👍/👎). (user_id, content_id) 단위 upsert."""
    try:
        if payload.feedback not in ["like", "dislike"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="feedback must be 'like' or 'dislike'"
            )

        result = supabase.table("content_feedback").upsert(
            {
                "session_id": payload.session_id,
                "user_id": payload.user_id,
                "content_id": payload.content_id,
                "feedback": payload.feedback,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id,content_id",
        ).execute()

        if result.data and len(result.data) > 0:
            feedback = result.data[0]

            # 모든 feedback 변경은 like 카운트에 영향을 줄 수 있으므로 취향 벡터 갱신
            from ai.tools.user_taste import refresh_user_taste_vector
            background_tasks.add_task(refresh_user_taste_vector, payload.user_id)

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


@router.delete("/feedback")
async def remove_content_feedback(
    user_id: str,
    content_id: str,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client),
):
    """좋아요/싫어요 토글 취소 — (user_id, content_id) row 제거."""
    try:
        result = (
            supabase.table("content_feedback")
            .delete()
            .eq("user_id", user_id)
            .eq("content_id", content_id)
            .execute()
        )

        deleted = len(result.data or [])
        if deleted > 0:
            from ai.tools.user_taste import refresh_user_taste_vector
            background_tasks.add_task(refresh_user_taste_vector, user_id)

        return {"deleted": deleted, "user_id": user_id, "content_id": content_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/watched")
async def record_watched_content(
    payload: WatchedContentRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """시청한 콘텐츠 기록"""
    try:
        row: dict = {
            "user_id": payload.user_id,
            "session_id": payload.session_id,
            "content_id": payload.content_id,
            "content_title": payload.content_title,
            "thumbnail_url": payload.thumbnail_url,
            "watched_at": datetime.now(timezone.utc).isoformat(),
        }
        if payload.media_provider is not None:
            row["media_provider"] = payload.media_provider
        if payload.media_url is not None:
            row["media_url"] = payload.media_url

        existing_result = (
            supabase.table("watched_content_records")
            .select("*")
            .eq("user_id", payload.user_id)
            .eq("content_id", payload.content_id)
            .order("watched_at", desc=True)
            .limit(20)
            .execute()
        )
        for existing in existing_result.data or []:
            if existing.get("session_id") == payload.session_id:
                return WatchedContentResponse(**existing)

        result = supabase.table("watched_content_records").insert(row).execute()

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


@router.get(
    "/recommendations/{user_id}",
    response_model=List[ContentRecommendationItem],
)
async def get_content_recommendations(
    user_id: str,
    limit: int = Query(8, ge=1, le=30),
    media: Literal["all", "youtube", "spotify"] = Query(
        "all",
        description="youtube | spotify | all (혼합)",
    ),
):
    """자동 추천 콘텐츠 시드 목록. user_id는 향후 개인화 시 사용."""
    _ = user_id
    now = datetime.now(timezone.utc).isoformat()
    if media == "all":
        filtered = _SEED_RECOMMENDATIONS[:limit]
    else:
        filtered = [
            x for x in _SEED_RECOMMENDATIONS if x.get("media_provider") == media
        ][:limit]

    return [
        ContentRecommendationItem(
            id=str(row["id"]),
            content_id=str(row["content_id"]),
            content_title=str(row["content_title"]),
            thumbnail_url=row.get("thumbnail_url"),
            media_provider=row.get("media_provider"),
            media_url=row.get("media_url"),
            watched_at=now,
            session_id=None,
        )
        for row in filtered
    ]


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
