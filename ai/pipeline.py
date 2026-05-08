"""
ai/pipeline.py

Assembles the 3-agent counseling pipeline.

Flow:
  1. Orchestrator  → crisis detection, intent classification, routing
  2. Counselor     → empathetic response with RAG + Function Calling
  3. Content Recommender → personalized search query (conditional)
"""

import logging

from ai.state import CounselingState
from ai.utils import load_crisis_response
from ai.agents.orchestrator import orchestrator_agent
from ai.agents.counselor import counselor_agent
from ai.agents.content_recommender import content_recommender_agent
from ai.tools.content_history import _get_supabase


logger = logging.getLogger(__name__)


def _short_id(value: str | None) -> str:
    return value[:8] if value else "-"


async def run_counseling_pipeline(
    user_id: str,
    session_id: str,
    message: str,
    messages: list[dict] | None = None,
) -> CounselingState:

    state = CounselingState(
        user_id=user_id,
        session_id=session_id,
        message=message,
        messages=messages or [],
    )

    # ① Orchestrator
    state = await orchestrator_agent(state)
    if state.is_crisis:
        state.response = load_crisis_response()
        return state

    # ② Counselor
    state = await counselor_agent(state)

    # ③ Content Recommender (conditional)
    if state.needs_recommendation:
        state = await content_recommender_agent(state)

        # ④ Post-processing: append recommendation info to counselor response
        if state.recommended_content:
            title = state.recommended_content.get("title", "")
            reason = state.recommended_content.get("reason", "")
            if title:
                state.response += f"\n\n'{title}'을(를) 추천해드릴게요. {reason}"

            # ⑤ Save recommended content to watched_content_records
            video_id = state.recommended_content.get("video_id")
            if video_id:
                try:
                    media_url = None
                    # 팟캐스트는 오디오 재생을 위해 media_url도 저장
                    if isinstance(video_id, str) and video_id.lower().startswith("podcast:"):
                        media_url = state.recommended_content.get("url")

                    supabase = _get_supabase()
                    row = {
                        "user_id": state.user_id,
                        "session_id": state.session_id,
                        "content_id": video_id,
                        "content_title": title,
                        "thumbnail_url": state.recommended_content.get("thumbnail", ""),
                    }
                    if media_url:
                        row["media_url"] = media_url

                    existing = (
                        supabase.table("watched_content_records")
                        .select("id")
                        .eq("user_id", state.user_id)
                        .eq("session_id", state.session_id)
                        .eq("content_id", video_id)
                        .limit(1)
                        .execute()
                    )
                    if not existing.data:
                        supabase.table("watched_content_records").insert(row).execute()

                    emotion = state.emotion_score.get("emotion_description", "")
                    intensity = float(state.emotion_score.get("intensity", 0.0))
                    supabase.table("recommendation_log").insert(
                        {
                            "user_id": state.user_id,
                            "session_id": state.session_id,
                            "search_query": state.recommended_content.get("search_query", ""),
                            "video_id": video_id,
                            "video_title": title,
                            "reason": reason,
                            "emotion": emotion,
                            "intensity": intensity,
                            "ambiguity": state.recommended_content.get("ambiguity"),
                            "secondary_emotion": state.recommended_content.get("secondary_emotion"),
                            "candidate_pool": state.recommended_content.get("candidate_pool", []),
                            "selected_score": state.recommended_content.get("selected_score", 0.0),
                            "strategy_version": "v2.1",
                        }
                    ).execute()
                except Exception as e:
                    # Non-fatal: don't break pipeline for a save failure
                    logger.warning(
                        "Recommendation log save failed user_id=%s session_id=%s content_id=%s error_type=%s",
                        _short_id(state.user_id),
                        _short_id(state.session_id),
                        _short_id(str(video_id)),
                        type(e).__name__,
                    )

    return state
