from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.supabase_service import get_supabase_client
from supabase import Client


router = APIRouter(prefix="/session", tags=["session"])


class SessionStartRequest(BaseModel):
    user_id: str
    context: Optional[str] = None


class SessionEndRequest(BaseModel):
    session_id: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    status: str
    started_at: str
    ended_at: Optional[str] = None


@router.post("/start", response_model=SessionResponse)
async def start_session(
    payload: SessionStartRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """새 상담 세션 시작"""
    try:
        result = supabase.table("counseling_sessions").insert({
            "user_id": payload.user_id,
            "status": "active",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        if result.data and len(result.data) > 0:
            session = result.data[0]
            return SessionResponse(**session)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/end", response_model=dict)
async def end_session(
    payload: SessionEndRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """상담 세션 종료"""
    try:
        result = supabase.table("counseling_sessions").update({
            "status": "ended",
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", payload.session_id).execute()

        if result.data and len(result.data) > 0:
            return {"status": "success", "session_id": payload.session_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/current/{user_id}", response_model=Optional[SessionResponse])
async def get_current_session(
    user_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """사용자의 현재 활성 세션 조회"""
    try:
        result = supabase.table("counseling_sessions").select("*").eq(
            "user_id", user_id
        ).eq("status", "active").order(
            "started_at", desc=True
        ).limit(1).execute()

        if result.data and len(result.data) > 0:
            session = result.data[0]
            return SessionResponse(**session)
        else:
            return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
