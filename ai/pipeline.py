"""
ai/pipeline.py

Assembles the 3-agent counseling pipeline.

Flow:
  1. Orchestrator  → crisis detection, intent classification, routing
  2. Counselor     → empathetic response with RAG + Function Calling
  3. Content Recommender → personalized search query (conditional)
"""

from ai.state import CounselingState
from ai.utils import load_crisis_response
from ai.agents.orchestrator import orchestrator_agent
from ai.agents.counselor import counselor_agent
from ai.agents.content_recommender import content_recommender_agent
from ai.tools.content_history import _get_supabase


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
                    supabase = _get_supabase()
                    # 5-1. watched_content_records
                    supabase.table("watched_content_records").insert({
                        "user_id": state.user_id,
                        "session_id": state.session_id,
                        "content_id": video_id,
                        "content_title": title,
                        "thumbnail_url": state.recommended_content.get("thumbnail", ""),
                    }).execute()
                    
                    # 5-2. recommendation_log
                    emotion = state.emotion_score.get("emotion_description", "")
                    intensity = float(abs(state.emotion_score.get("valence", 0.0)))
                    
                    supabase.table("recommendation_log").insert({
                        "user_id": state.user_id,
                        "session_id": state.session_id,
                        "search_query": state.recommended_content.get("search_query", ""),
                        "video_id": video_id,
                        "video_title": title,
                        "reason": reason,
                        "emotion": emotion,
                        "intensity": intensity,
                        "candidate_pool": state.recommended_content.get("candidate_pool", []),
                        "selected_score": state.recommended_content.get("selected_score", 0.0),
                        "strategy_version": "v2.1"
                    }).execute()
                except Exception as e:
                    print(f"Failed to save recommendation log/history: {e}")

    return state
