"""
ai/agents/content_recommender.py

유저 의도에 따라 콘텐츠 추천을 수행합니다.

  - intent == "추천": 기본 YouTube; 웰니스(명상·수면·가이드 등)면 팟캐스트 우선 시도
  - 특정 곡·플레이리스트·일반 음악으로 보이면(`likely_music_search_request`) 팟캐스트 스킵
  - intent != "추천": 웰니스 맥락에서 팟캐스트 우선(음악 검색으로 보이면 스킵)
  - 사용자가 말/가이드 없이 음악·BGM만 원하면(`wants_music_only_bgm`) 팟캐스트를 건너뛰고
    YouTube 검색 쿼리에 인스트루멘탈·no talking 등을 반영

- GPT를 이용해 검색 쿼리 생성
- MCP 서버를 통해 YouTube 검색 및 팟캐스트(RSS 큐레이션) 추천
- reranker를 통한 하이브리드 재랭킹 수행
"""
import os
import json
from pathlib import Path

from openai import OpenAI
from fastmcp import Client as MCPClient

from ai.config import OPENAI_API_KEY
from ai.state import CounselingState
from ai.utils import load_prompt
from ai.tools.content_history import get_content_history, _get_supabase, get_recent_liked_titles
from ai.tools.user_profile import get_user_profile
from ai.tools.emotion_va_map import compute_emotion_ambiguity
from ai.agents.reranker import compute_emotion_trend, hybrid_rerank
from ai.meditation_audio_clarify import meditation_audio_format_applies_to_current_message
from ai.meditation_audio_signals import (
    has_wellness_context,
    likely_music_search_request,
    wants_music_only_bgm,
    wants_podcast,
)

try:
    from ai.tools.podcast_catalog import recommend_podcast_episode as _recommend_podcast_direct
except Exception:  # pragma: no cover
    _recommend_podcast_direct = None  # type: ignore[misc, assignment]

# MCP 서버 경로 (환경 변수로 오버라이드 가능)
_DEFAULT_MCP_SERVER_PATH = str(Path(__file__).parent.parent.parent / "mcp_servers" / "server.py")
_MCP_SERVER_PATH = os.getenv("MCP_SERVER_PATH", _DEFAULT_MCP_SERVER_PATH)
_MODEL = "gpt-4o-mini"


async def _recommend_podcast_via_mcp(emotion: str, intensity: float, watched_ids: list[str]) -> dict | None:
    async with MCPClient(_MCP_SERVER_PATH) as mcp:
        mcp_result = await mcp.call_tool(
            "recommend_podcast_episode",
            {
                "emotion": emotion,
                "intensity": float(intensity),
                "watched_content_ids": watched_ids,
            },
        )
        raw_text = mcp_result.content[0].text if mcp_result.content else "null"
        episode = json.loads(raw_text)
        if episode and isinstance(episode, dict) and episode.get("content_id"):
            return episode
    return None


def _recommend_podcast_direct_sync(emotion: str, intensity: float, watched_ids: list[str]) -> dict | None:
    if _recommend_podcast_direct is None:
        return None
    try:
        ep = _recommend_podcast_direct(
            emotion=emotion,
            intensity=float(intensity),
            watched_content_ids=watched_ids,
        )
        if ep and ep.get("content_id"):
            return ep
    except Exception as e:
        print(f"direct podcast_catalog failed: {e}", flush=True)
    return None


def _get_openai() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env.local")
    return OpenAI(api_key=OPENAI_API_KEY)

async def content_recommender_agent(state: CounselingState) -> CounselingState:
    # ── 1. User profile ─────────────
    profile = state.user_profile
    if not profile:
        profile = get_user_profile(state.user_id)
        state.user_profile = profile

    concerns = ", ".join(profile.get("concerns", [])) or "없음"
    comfort_style = ", ".join(profile.get("comfort_style", [])) or "음악"

    # ── 2. Content history ──────────────────────────────────────────────
    history = get_content_history(state.user_id)
    watched_ids = history.get("watched_ids", [])

    # 최근 좋아요 영상 제목을 검색 쿼리 생성용 힌트로 사용
    liked_titles = get_recent_liked_titles(state.user_id, limit=5)
    liked_hints = " | ".join(t[:60] for t in liked_titles) or "없음"

    # print(f"[DEBUG] user={state.user_id[:8]} liked_hints={liked_hints!r}", flush=True) # for debug


    # ── 2.5 감정 궤적(Trend) 파악 ───────────────────────────────────────
    supabase = _get_supabase()
    emotion_result = supabase.table("emotion_records").select("*") \
        .eq("user_id", state.user_id).order("created_at", desc=True).limit(3).execute()
    emotion_records = emotion_result.data if emotion_result.data else []
    
    trend_info = compute_emotion_trend(emotion_records)
    trend = trend_info["trend"]

    # ── 3. Build prompt with template substitution ──────────────────────
    emotion = state.emotion_score.get("emotion", "스트레스")
    intensity = state.emotion_score.get("intensity", 0.5)
    valence = state.emotion_score.get("valence", 0.0)
    arousal = state.emotion_score.get("arousal", 0.0)

    # 좌표 기반 감정 분류 모호성 — 두 라벨 사이에 끼어 있을 때 secondary 채워짐
    ambiguity_info = compute_emotion_ambiguity(valence, arousal)
    secondary_emotion = ambiguity_info["secondary"] or "없음"
    ambiguity = ambiguity_info["ambiguity"]

    # ── 3.5 팟캐스트 추천 (선택) ───────────────────────────────────────────
    applies = meditation_audio_format_applies_to_current_message(state) or (
        state.meditation_format_resolved_this_turn and bool(state.meditation_audio_format)
    )
    stored_music = state.meditation_audio_format == "music_only" and applies
    # 확인 질문으로 guided 확정된 같은 턴(meditation_format_resolved_this_turn)에는 applies가 비어도 반영
    # 세션 guided + 추천 intent + 웰니스 맥락이면 직전에 고른 가이드형 유지
    stored_guided = bool(state.meditation_audio_format == "guided") and (
        applies
        or state.meditation_format_resolved_this_turn
        or (
            state.needs_recommendation
            and state.intent == "추천"
            and has_wellness_context(state.message)
        )
    )
    wants_music_only = wants_music_only_bgm(state.message) or stored_music
    likely_music = likely_music_search_request(state.message)
    # stored_guided: 확인 질문 직후 짧은 답 등에서 wants_podcast가 약할 때 보강
    prefer_podcast = (
        (wants_podcast(state.message) or stored_guided) and not wants_music_only and not likely_music
    )
    # 추천 intent일 때도 가이드형 세션/선호가 있으면 팟캐스트 후보 시도 (유튜브만 나가는 회귀 방지)
    try_podcast = (
        not wants_music_only
        and not likely_music
        and (prefer_podcast or state.intent != "추천")
    )
    if try_podcast:
        episode = None
        try:
            episode = await _recommend_podcast_via_mcp(emotion, intensity, watched_ids)
        except Exception as e:
            print(f"MCP podcast failed: {e}", flush=True)
        if not episode:
            episode = _recommend_podcast_direct_sync(emotion, intensity, watched_ids)

        if episode and isinstance(episode, dict) and episode.get("content_id"):
            state.recommended_content = {
                "video_id": episode.get("content_id"),
                "title": episode.get("title", ""),
                "url": episode.get("audio_url", ""),
                "thumbnail": episode.get("thumbnail_url", ""),
                "reason": episode.get("reason", "지금의 감정에 맞춰 마음을 정리해주는 가이드를 추천드려요."),
            }
            return state
    prompt_template = load_prompt("content_recommender_prompt.md")
    user_prompt = prompt_template.format(
        emotion=emotion,
        secondary_emotion=secondary_emotion,
        intensity=intensity,
        concerns=concerns,
        comfort_style=comfort_style,
        liked_hints=liked_hints,
    )

    music_only_note = ""
    if wants_music_only:
        music_only_note = (
            "\n[중요] 사용자는 말·내레이션·가이드 멘트 없이 "
            "**순수 음악·배경음(인스트루멘탈)** 위주를 원합니다. "
            "검색 쿼리에 `instrumental`, `no talking`, `피아노`, `자연`, `ambient`, `힐링 음악` 등을 "
            "적절히 넣어 주세요. `guided meditation`, `명상 가이드` 같은 표현은 피하세요.\n"
        )

    # ── 4. GPT call for query generation (Trend 반영) ───────────────────
    client = _get_openai()
    response = client.chat.completions.create(
        model=_MODEL,
        temperature=0.7,
        max_tokens=200,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": user_prompt},
            {
                "role": "user",
                "content": (
                    f"사용자 요청: {state.message}\n"
                    f"현재 감정: {emotion} (인접 감정: {secondary_emotion}, 강도: {intensity}, 트렌드: {trend})\n"
                    f"고민: {concerns}\n"
                    f"위로 방식: {comfort_style}\n"
                    f"좋아한 콘텐츠 제목들: {liked_hints}\n"
                    f"{music_only_note}"
                ),
            },
        ],
    )

    raw = response.choices[0].message.content or "{}"
    result = json.loads(raw)
    search_query = result.get("search_query", "healing music relaxing")
    reason = result.get("reason", "마음을 편안하게 해줄 콘텐츠를 추천드려요.")
    videos = []
    try:
        async with MCPClient(_MCP_SERVER_PATH) as mcp:
            mcp_result = await mcp.call_tool(
                "search_youtube",
                {"query": search_query, "watched_ids": watched_ids, "max_results": 10},
            )
            videos = json.loads(mcp_result.content[0].text) if mcp_result.content else []
            if videos and "error" in videos[0]:
                videos = []
    except Exception as e:
        print(f"MCP Call Failed: {e}")

    # ── 6. 하이브리드 재랭킹 (NEW) ──────────────────────────────────────
    video = None
    candidate_pool = []
    selected_score = 0.0
    
    if videos:
        # candidates의 형식을 통일
        formatted_cands = []
        for v in videos:
            v_copy = v.copy()
            if "video_id" in v_copy and "content_id" not in v_copy:
                v_copy["content_id"] = v_copy["video_id"]
            formatted_cands.append(v_copy)
            
        emotion_description = state.emotion_score.get("emotion_description", "")
            
        ranked_videos = await hybrid_rerank(
            formatted_cands, 
            state.user_id, 
            state.session_id, 
            emotion, 
            intensity, 
            emotion_records, 
            comfort_style,
            emotion_description=emotion_description
        )
        
        if ranked_videos:
            video = ranked_videos[0]
            selected_score = video.get("score", 0.0)
            candidate_pool = [{"video_id": v.get("content_id"), "score": v.get("score", 0.0)} for v in ranked_videos]

    # ── 7. Store result ─────────────────────────────────────────────────
    secondary_for_log = ambiguity_info["secondary"]  # None일 수 있음 (모호 임계 미충족)
    if video:
        state.recommended_content = {
            "video_id": video.get("content_id") or video.get("video_id"),
            "title": video.get("title", ""),
            "url": video.get("url", ""),
            "thumbnail": video.get("thumbnail", ""),
            "reason": reason,
            "search_query": search_query,
            "candidate_pool": candidate_pool,
            "selected_score": selected_score,
            "ambiguity": ambiguity,
            "secondary_emotion": secondary_for_log,
        }
    else:
        state.recommended_content = {
            "search_query": search_query,
            "reason": reason,
            "ambiguity": ambiguity,
            "secondary_emotion": secondary_for_log,
        }

    return state
