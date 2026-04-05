from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.supabase_service import get_supabase_client
from supabase import Client


router = APIRouter(prefix="/user", tags=["user"])


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: str


class UserProfileUpsertRequest(BaseModel):
    user_id: str
    display_name: str


@router.get("/profile/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자 프로필 조회"""
    try:
        profile_result = supabase.table("user_profiles").select(
            "display_name, created_at"
        ).eq("user_id", user_id).limit(1).execute()

        if profile_result.data and len(profile_result.data) > 0:
            profile = profile_result.data[0]
            return {
                "id": user_id,
                "email": f"user_{user_id[:8]}@moodpick.local",  # 임시
                "name": profile.get("display_name") or f"User {user_id[:4]}",
                "avatar_url": None,
                "created_at": profile["created_at"],
            }

        session_result = supabase.table("counseling_sessions").select(
            "created_at"
        ).eq("user_id", user_id).order("created_at", desc=False).limit(1).execute()

        created_at = (
            session_result.data[0]["created_at"]
            if session_result.data and len(session_result.data) > 0
            else "1970-01-01T00:00:00+00:00"
        )

        return {
            "id": user_id,
            "email": f"user_{user_id[:8]}@moodpick.local",
            "name": f"User {user_id[:4]}",
            "avatar_url": None,
            "created_at": created_at,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/profile")
async def upsert_user_profile(
    payload: UserProfileUpsertRequest,
    supabase: Client = Depends(get_supabase_client),
):
    """사용자 프로필 이름 저장/수정"""
    try:
        display_name = payload.display_name.strip()
        if not display_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="display_name is required",
            )

        result = supabase.table("user_profiles").upsert(
            {
                "user_id": payload.user_id,
                "display_name": display_name,
            },
            on_conflict="user_id",
        ).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                "status": "success",
                "user_id": row["user_id"],
                "display_name": row["display_name"],
            }

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upsert user profile",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/sessions/{user_id}")
async def get_user_sessions(
    user_id: str,
    limit: int = 10,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자의 세션 목록 조회 (최근 10개)"""
    try:
        result = supabase.table("counseling_sessions").select("*").eq(
            "user_id", user_id
        ).order("started_at", desc=True).limit(limit).execute()

        if result.data:
            return {
                "user_id": user_id,
                "sessions": result.data
            }
        return {
            "user_id": user_id,
            "sessions": []
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats/{user_id}")
async def get_user_stats(
    user_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자 통계 (세션, 피드백, 시청 기록)"""
    try:
        # 세션 수
        sessions = supabase.table("counseling_sessions").select(
            "id"
        ).eq("user_id", user_id).execute()
        total_sessions = len(sessions.data) if sessions.data else 0

        # 시청 기록
        watched = supabase.table("watched_content_records").select(
            "id"
        ).eq("user_id", user_id).execute()
        total_watched = len(watched.data) if watched.data else 0

        # 피드백
        feedback = supabase.table("content_feedback").select(
            "feedback"
        ).eq("user_id", user_id).execute()
        
        total_feedback = len(feedback.data) if feedback.data else 0
        likes = len([f for f in feedback.data if f["feedback"] == "like"]) if feedback.data else 0

        return {
            "user_id": user_id,
            "total_sessions": total_sessions,
            "total_content_watched": total_watched,
            "total_feedback": total_feedback,
            "likes": likes,
            "dislikes": total_feedback - likes
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
