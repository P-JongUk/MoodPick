"""
backend/app/services/ai_service.py

Thin wrapper around the ai/ pipeline.
Catches exceptions to guarantee a fallback response (no conversation breakage).
"""

from ai.pipeline import run_counseling_pipeline


async def get_ai_response(
    user_id: str,
    session_id: str,
    message: str,
    messages: list[dict] | None = None,
) -> dict:
    try:
        state = await run_counseling_pipeline(
            user_id=user_id,
            session_id=session_id,
            message=message,
            messages=messages,
        )
        return {
            "message": state.response,
            "emotion": state.emotion_score,
            "recommended_content": state.recommended_content,
        }
    except Exception:
        return {
            "message": "지금 감정을 한 문장으로 표현해 보면 원인을 더 명확히 찾는 데 도움이 돼요.",
            "emotion": {},
            "recommended_content": None,
        }
