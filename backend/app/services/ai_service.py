"""
backend/app/services/ai_service.py

Thin wrapper around the ai/ pipeline.
Catches exceptions to guarantee a fallback response (no conversation breakage).
"""

import logging
from typing import AsyncGenerator

from ai.pipeline import run_counseling_pipeline, run_counseling_pipeline_stream


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
        recommended_content = state.recommended_content
        if isinstance(recommended_content, dict):
            recommended_content = dict(recommended_content)
            recommended_content.pop("search_query", None)
        return {
            "message": state.response,
            "is_crisis": state.is_crisis,
            "emotion": state.emotion_score,
            "recommended_content": recommended_content,
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
            "message": "지금 답변을 만드는 중 잠시 문제가 생겼어요. 괜찮다면 방금 이야기해 준 내용을 한 번만 다시 보내주세요.",
            "is_crisis": False,
            "emotion": {},
            "recommended_content": None,
            "fallback": True,
            "error_type": "ai_unavailable",
        }


async def get_ai_response_stream(
    user_id: str,
    session_id: str,
    message: str,
    messages: list[dict] | None = None,
    session_summary: str | None = None,
    persona: str = "expert",
) -> AsyncGenerator[dict, None]:
    """run_counseling_pipeline_stream의 얇은 래퍼. 예외 발생 시 error 이벤트를 yield한다."""
    try:
        async for event in await run_counseling_pipeline_stream(
            user_id=user_id,
            session_id=session_id,
            message=message,
            messages=messages,
            session_summary=session_summary,
            persona=persona,
        ):
            if event.get("type") == "done" and isinstance(event.get("recommended_content"), dict):
                event = dict(event)
                recommended_content = dict(event["recommended_content"])
                recommended_content.pop("search_query", None)
                event["recommended_content"] = recommended_content
            yield event
    except Exception as exc:
        logger.warning(
            "AI pipeline stream failed user_id=%s session_id=%s error_type=%s",
            _short_id(user_id),
            _short_id(session_id),
            type(exc).__name__,
        )
        yield {
            "type": "error",
            "message": "AI 상담 응답을 만드는 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
        }
