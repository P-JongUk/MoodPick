from datetime import datetime, timedelta, timezone
import logging
from typing import Literal, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.supabase_service import get_supabase_client
from supabase import Client


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["session"])

# 마지막 메시지(또는 세션 시작) 이후 이 시간이 지나면 자동 종료 대상
STALE_SESSION_HOURS = 36

CounselorPersona = Literal["friend", "teacher", "expert"]


class SessionStartRequest(BaseModel):
    user_id: str
    context: Optional[str] = None
    persona: CounselorPersona = "expert"


class SessionEndRequest(BaseModel):
    session_id: str


class StaleSessionCleanupRequest(BaseModel):
    user_id: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    status: str
    started_at: str
    ended_at: Optional[str] = None
    persona: CounselorPersona = "expert"


@router.post("/start", response_model=SessionResponse)
async def start_session(
    payload: SessionStartRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """새 상담 세션 시작 (사용자당 동시 active는 하나만 유지)"""
    try:
        now = datetime.now(timezone.utc).isoformat()
        # 프론트/네트워크 실수로 active가 여러 개면 종료한 세션만 ended 되고 나머지가 남을 수 있음
        (
            supabase.table("counseling_sessions")
            .update({"status": "ended", "ended_at": now})
            .eq("user_id", payload.user_id)
            .eq("status", "active")
            .execute()
        )

        result = supabase.table("counseling_sessions").insert({
            "user_id": payload.user_id,
            "status": "active",
            "started_at": now,
            "persona": payload.persona,
        }).execute()

        if result.data and len(result.data) > 0:
            session = result.data[0]
            return SessionResponse(**session)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
    except HTTPException:
        raise
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
        now = datetime.now(timezone.utc).isoformat()
        # select()와 함께 PATCH하면 환경에 따라 data가 비어 404→500으로 잘못 전달되는 경우가 있어,
        # cleanup-stale과 동일하게 update만 실행한 뒤 별도 조회로 검증합니다.
        (
            supabase.table("counseling_sessions")
            .update(
                {
                    "status": "ended",
                    "ended_at": now,
                }
            )
            .eq("id", payload.session_id)
            .execute()
        )

        verify = (
            supabase.table("counseling_sessions")
            .select("id", "status", "user_id")
            .eq("id", payload.session_id)
            .limit(1)
            .execute()
        )
        rows = verify.data or []
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        if rows[0].get("status") != "ended":
            logger.warning(
                "end_session: session %s still active after update (status=%s)",
                payload.session_id,
                rows[0].get("status"),
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="세션을 종료하지 못했어요. 잠시 후 다시 시도해 주세요.",
            )
        # 동시에 active였던 고아 세션(예: 같은 날 재시작 버그)이 남으면 재접속 시 이어가기가 뜸
        owner_id = rows[0].get("user_id")
        if owner_id:
            (
                supabase.table("counseling_sessions")
                .update({"status": "ended", "ended_at": now})
                .eq("user_id", owner_id)
                .eq("status", "active")
                .execute()
            )
        return {"status": "success", "session_id": payload.session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("end_session failed session_id=%s", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def _parse_ts(value: str) -> datetime:
    """Supabase timestamptz ISO 문자열을 UTC aware datetime으로."""
    raw = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/cleanup-stale", response_model=dict)
async def cleanup_stale_sessions_for_user(
    payload: StaleSessionCleanupRequest,
    supabase: Client = Depends(get_supabase_client),
):
    """
    사용자 기준으로 오래 방치된 active 세션을 ended로 정리합니다.
    (로그인 직후 등에서 호출 — 사후 문진 없이 종료 처리)
    """
    try:
        sessions_result = (
            supabase.table("counseling_sessions")
            .select("id, started_at")
            .eq("user_id", payload.user_id)
            .eq("status", "active")
            .execute()
        )
        sessions = sessions_result.data or []
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=STALE_SESSION_HOURS)
        closed_ids: list[str] = []

        # 동시에 active가 여러 개면(과거 동일 날 재시작 버그 등) 최신 세션만 남기고 나머지 종료
        if len(sessions) > 1:
            sorted_sess = sorted(
                sessions,
                key=lambda s: _parse_ts(str(s["started_at"])) if s.get("started_at") else now,
                reverse=True,
            )
            for s in sorted_sess[1:]:
                sid = str(s["id"])
                supabase.table("counseling_sessions").update(
                    {
                        "status": "ended",
                        "ended_at": now.isoformat(),
                    }
                ).eq("id", sid).execute()
                closed_ids.append(sid)
            sessions_result = (
                supabase.table("counseling_sessions")
                .select("id, started_at")
                .eq("user_id", payload.user_id)
                .eq("status", "active")
                .execute()
            )
            sessions = sessions_result.data or []

        for s in sessions:
            sid = str(s["id"])
            started_raw = s.get("started_at")
            started_at = _parse_ts(str(started_raw)) if started_raw else now

            last_row = (
                supabase.table("counseling_history")
                .select("created_at")
                .eq("session_id", sid)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if last_row.data:
                last_activity = _parse_ts(str(last_row.data[0]["created_at"]))
            else:
                last_activity = started_at

            if last_activity < threshold:
                supabase.table("counseling_sessions").update(
                    {
                        "status": "ended",
                        "ended_at": now.isoformat(),
                    }
                ).eq("id", sid).execute()
                closed_ids.append(sid)

        return {
            "status": "ok",
            "closed_session_ids": closed_ids,
            "closed_count": len(closed_ids),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
