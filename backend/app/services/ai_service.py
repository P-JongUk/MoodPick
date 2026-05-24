"""
backend/app/services/ai_service.py

Thin wrapper around the ai/ pipeline.
Catches exceptions to guarantee a fallback response (no conversation breakage).
"""

import logging

from ai.pipeline import run_counseling_pipeline


logger = logging.getLogger(__name__)


def _short_id(value: str | None) -> str:
    return value[:8] if value else "-"


async def get_ai_response(
    user_id: str,
    session_id: str,
    message: str,
    messages: list[dict] | None = None,
    session_summary: str | None = None,
    persona: str = "expert",
) -> dict:
    try:
        state = await run_counseling_pipeline(
            user_id=user_id,
            session_id=session_id,
            message=message,
            messages=messages,
            session_summary=session_summary,
            persona=persona,
        )
        return {
            "message": state.response,
            "is_crisis": state.is_crisis,
            "emotion": state.emotion_score,
            "recommended_content": state.recommended_content,
            "fallback": False,
        }
    except Exception as exc:
        logger.warning(
            "AI pipeline failed user_id=%s session_id=%s error_type=%s",
            _short_id(user_id),
            _short_id(session_id),
            type(exc).__name__,
        )
        return {
            "message": "지금 감정을 한 문장으로 표현해 보면 원인을 더 명확히 찾는 데 도움이 돼요.",
            "is_crisis": False,
            "emotion": {},
            "recommended_content": None,
            "fallback": True,
            "error_type": "ai_unavailable",
        }
