from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.services.supabase_service import get_supabase_client


router = APIRouter(prefix="/counseling", tags=["counseling"])


class CounselingMessageRequest(BaseModel):
    user_id: str
    message: str
    session_id: str | None = None


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
):
    try:
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/message")
async def send_counseling_message(payload: CounselingMessageRequest):
    guidance = "지금 감정을 한 문장으로 표현해 보면 원인을 더 명확히 찾는 데 도움이 돼요."
    if len(payload.message.strip()) < 10:
        guidance = "좋아요. 한두 문장만 더 덧붙여 주시면 더 정확하게 정리해드릴 수 있어요."

    return {
        "message": guidance,
        "user_id": payload.user_id,
        "echo": payload.message,
        "session_id": payload.session_id,
        "status": "ok",
    }
