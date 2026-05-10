"""
ai/pipeline.py

Assembles the 3-agent counseling pipeline.

Flow:
  1. Orchestrator  → crisis detection, intent classification, routing
  2. Counselor     → empathetic response with RAG + Function Calling
  3. Content Recommender → personalized search query (conditional)
"""

import logging
import time

from ai.state import CounselingState
from ai.utils import load_crisis_response
from ai.agents.orchestrator import orchestrator_agent
from ai.agents.counselor import counselor_agent
from ai.agents.content_recommender import content_recommender_agent
from ai.tools.content_history import _get_supabase
from ai.tools.session_meditation_format import (
    get_session_meditation_audio_format,
    set_session_meditation_audio_format,
)
from ai.meditation_audio_clarify import (
    MEDITATION_FORMAT_CLARIFICATION,
    is_reply_to_meditation_format_clarification,
    parse_meditation_format_reply,
    should_ask_meditation_format_clarification,
)


logger = logging.getLogger(__name__)


def _short_id(value: str | None) -> str:
    return value[:8] if value else "-"


async def run_counseling_pipeline(
    user_id: str,
    session_id: str,
    message: str,
    messages: list[dict] | None = None,
) -> CounselingState:

    _perf_t0 = time.perf_counter()
    state = CounselingState(
        user_id=user_id,
        session_id=session_id,
        message=message,
        messages=messages or [],
    )
    try:
        _fmt = get_session_meditation_audio_format(session_id)
        if _fmt:
            state.meditation_audio_format = _fmt
    except Exception:
        pass

    # ① Orchestrator
    _t = time.perf_counter()
    state = await orchestrator_agent(state)
    logger.info("[PERF] orchestrator=%.3fs", time.perf_counter() - _t)
    if state.is_crisis:
        state.response = load_crisis_response()
        logger.info("[PERF] total(crisis)=%.3fs", time.perf_counter() - _perf_t0)
        return state

    # ② Counselor
    _t = time.perf_counter()
    state = await counselor_agent(state)
    logger.info("[PERF] counselor=%.3fs", time.perf_counter() - _t)

    # 직전 클라리피 응답에 답하는 턴 처리.
    # 명확한 "가이드"/"음악만" 답변일 때만 세션 저장하고 추천 진입을 강제한다.
    # 모호한 답이면 새 요청으로 해석되도록 그대로 통과 — 오케스트레이터 판단 신뢰.
    replying_meditation_format = is_reply_to_meditation_format_clarification(
        state.messages, state.message
    )
    if replying_meditation_format:
        _reply_fmt = parse_meditation_format_reply(state.message)
        if _reply_fmt is not None:
            try:
                set_session_meditation_audio_format(session_id, _reply_fmt)
            except Exception as e:
                logger.warning(
                    "Meditation audio format save skipped session_id=%s error_type=%s",
                    _short_id(session_id),
                    type(e).__name__,
                )
            state.meditation_audio_format = _reply_fmt
            state.needs_recommendation = True
            state.meditation_format_resolved_this_turn = True
            # 한 단어 답변("가이드"/"음악만")을 오케스트레이터가 unspecified로 잘못
            # 분류하더라도 라우팅이 깨지지 않도록 content_format을 강제 설정한다.
            # - "guided" → audio (팟캐스트 가이드 에피소드)
            # - "music_only" → music (YouTube 인스트루멘탈/BGM 검색)
            state.content_format = "audio" if _reply_fmt == "guided" else "music"

    # ③ Content Recommender (conditional)
    if state.needs_recommendation:
        if should_ask_meditation_format_clarification(state):
            state.response += MEDITATION_FORMAT_CLARIFICATION
            logger.info("[PERF] total(clarify)=%.3fs", time.perf_counter() - _perf_t0)
            return state

        _t = time.perf_counter()
        state = await content_recommender_agent(state)
        logger.info("[PERF] content_recommender=%.3fs", time.perf_counter() - _t)

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

                    _t_db = time.perf_counter()
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
                    logger.info("[PERF] post_db_save=%.3fs", time.perf_counter() - _t_db)
                except Exception as e:
                    # Non-fatal: don't break pipeline for a save failure
                    logger.warning(
                        "Recommendation log save failed user_id=%s session_id=%s content_id=%s error_type=%s",
                        _short_id(state.user_id),
                        _short_id(state.session_id),
                        _short_id(str(video_id)),
                        type(e).__name__,
                    )

    logger.info("[PERF] total=%.3fs", time.perf_counter() - _perf_t0)
    return state
