import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import CurrentUser, get_current_user, get_owned_session, require_same_user
from app.services.supabase_service import get_supabase_client
from app.services.ai_service import get_ai_response
from app.services.session_summary import prepare_session_context


router = APIRouter(prefix="/counseling", tags=["counseling"])
logger = logging.getLogger(__name__)

# 프론트 `sendCounselingMessage`와 동일 — DB에는 본문만 저장·히스토리 응답에서 제거
COUNSELING_USER_MARKDOWN_SUFFIX = "\n\n마크다운 형식으로 제공해."


def _strip_user_markdown_suffix(text: str) -> str:
    if text.endswith(COUNSELING_USER_MARKDOWN_SUFFIX):
        return text[: -len(COUNSELING_USER_MARKDOWN_SUFFIX)]
    return text


class CounselingMessageRequest(BaseModel):
    user_id: str
    message: str
    session_id: str | None = None


def _short_id(value: str | None) -> str:
    return value[:8] if value else "-"


MOOD_MESSAGE_MAP = {
    "great": "좋은 흐름을 이어가 볼까요? 오늘 긍정적인 순간을 더 크게 만들 방법을 같이 찾아봐요.",
    "good": "현재의 균형을 잘 유지하고 계시네요. 오늘 가장 안정감을 준 순간을 함께 정리해볼게요.",
    "neutral": "괜찮아요. 지금 상태를 천천히 살펴보면서 부담 없이 대화를 시작해볼게요.",
    "low": "조금 지친 상태일 수 있어요. 우선 숨을 고르고, 지금 가장 무거운 부분부터 하나씩 풀어봐요.",
    "bad": "많이 힘든 상태로 보여요. 지금 여기서는 안전하게 감정을 표현해도 괜찮아요. 천천히 시작해요.",
}


def _build_initial_message(mood_value: str | None) -> str:
    if mood_value:
        return MOOD_MESSAGE_MAP.get(
            mood_value,
            "오늘의 마음 상태를 바탕으로 천천히 대화를 이어갈게요. 편하게 이야기해 주세요.",
        )
    return "안녕하세요, 저는 무드픽 상담사입니다. 오늘 하루 어떠셨나요? 편하게 이야기해 주세요."


@router.get("/initial-message/{session_id}")
async def get_initial_counseling_message(
    session_id: str,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        get_owned_session(supabase, session_id, current_user.id)
        response = supabase.table("survey_responses").select(
            "emoji_value"
        ).eq("session_id", session_id).eq("phase", "pre").eq(
            "question_key", "mood_general"
        ).order("created_at", desc=True).limit(1).execute()

        mood_value = None
        if response.data and len(response.data) > 0:
            mood_value = response.data[0].get("emoji_value")

        return {
            "session_id": session_id,
            "mood": mood_value,
            "message": _build_initial_message(mood_value),
            "status": "ok",
        }
    except Exception as e:
        logger.warning(
            "Initial counseling message failed session_id=%s error_type=%s",
            _short_id(session_id),
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="초기 상담 메시지를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
        )


def _get_session_for_user(supabase: Client, session_id: str, user_id: str) -> dict:
    result = (
        supabase.table("counseling_sessions")
        .select("id,user_id,status")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상담 세션을 찾을 수 없어요. 새 상담을 시작해 주세요.",
        )
    return result.data[0]


@router.get("/history/{session_id}")
async def get_counseling_history(
    session_id: str,
    user_id: str = Query(..., description="Supabase auth user id"),
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    """상담 세션의 저장된 대화 목록(시간순)."""
    try:
        require_same_user(user_id, current_user)
        _get_session_for_user(supabase, session_id, user_id)
        hist = (
            supabase.table("counseling_history")
            .select("id, role, content, created_at")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        rows = list(hist.data or [])
        out_rows: list[dict] = []
        for row in rows:
            r = dict(row)
            if r.get("role") == "user" and isinstance(r.get("content"), str):
                r["content"] = _strip_user_markdown_suffix(r["content"])
            out_rows.append(r)
        return {"session_id": session_id, "messages": out_rows}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(
            "Counseling history failed session_id=%s error_type=%s",
            _short_id(session_id),
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="상담 기록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
        ) from e


def _save_message(supabase: Client, session_id: str, user_msg: str, ai_msg: str) -> None:
    """Persist the user message and AI response to DB."""
    user_stored = _strip_user_markdown_suffix(user_msg)
    supabase.table("counseling_history").insert([
        {"session_id": session_id, "role": "user", "content": user_stored},
        {"session_id": session_id, "role": "assistant", "content": ai_msg},
    ]).execute()


@router.post("/message")
async def send_counseling_message(
    payload: CounselingMessageRequest,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    if not payload.session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="상담 시작 후 메시지를 보내 주세요.",
        )

    try:
        require_same_user(payload.user_id, current_user)
        session = _get_session_for_user(supabase, payload.session_id, payload.user_id)
        if session.get("status") == "ended":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 종료된 상담이에요. 새 상담을 시작해 주세요.",
            )

        user_plain = _strip_user_markdown_suffix(payload.message)

        # 1. Build conversation context (recent N turns + summary if threshold exceeded)
        summary, history = await prepare_session_context(supabase, payload.session_id)

        # 2. Run AI pipeline (원문+접미사로 마크다운 지시, DB에는 본문만 저장)
        result = await get_ai_response(
            user_id=payload.user_id,
            session_id=payload.session_id,
            message=payload.message,
            messages=history,
            session_summary=summary,
        )

        # 3. Save this turn to DB
        _save_message(supabase, payload.session_id, user_plain, result["message"])

        return {**result, "status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(
            "Counseling message failed user_id=%s session_id=%s error_type=%s",
            _short_id(payload.user_id),
            _short_id(payload.session_id),
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="상담 메시지 처리 중 오류가 발생했어요. 잠시 후 다시 시도해 주세요.",
        )
