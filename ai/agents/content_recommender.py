"""
ai/agents/content_recommender.py

사용자의 감정 상태와 취향을 분석하여 최적의 콘텐츠를 추천하는 에이전트.

- GPT를 이용해 검색 쿼리 생성
- MCP YouTube 서버를 통해 후보군 검색
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
from ai.tools.content_history import get_content_history, _get_supabase
from ai.tools.user_profile import get_user_profile
from ai.agents.reranker import compute_emotion_trend, hybrid_rerank

# MCP 서버 경로 (환경 변수로 오버라이드 가능)
_DEFAULT_MCP_SERVER_PATH = str(Path(__file__).parent.parent.parent / "mcp_servers" / "server.py")
_MCP_SERVER_PATH = os.getenv("MCP_SERVER_PATH", _DEFAULT_MCP_SERVER_PATH)
_MODEL = "gpt-4o-mini"

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
    # 수정 필요

    prompt_template = load_prompt("content_recommender_prompt.md")
    user_prompt = prompt_template.format(
        emotion=emotion,
        intensity=intensity,
        concerns=concerns,
        comfort_style=comfort_style,
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
                    f"현재 감정: {emotion} (강도: {intensity}, 트렌드: {trend})\n"
                    f"고민: {concerns}\n"
                    f"위로 방식: {comfort_style}\n"
                ),
            },
        ],
    )

    raw = response.choices[0].message.content or "{}"
    result = json.loads(raw)
    
    # query_generation만 GPT로 함
    search_query = result.get("search_query", "healing music relaxing")
    reason = result.get("reason", "마음을 편안하게 해줄 콘텐츠를 추천드려요.")

    # ── 5. MCP YouTube 서버 호출 (10개로 증가) ──────────────────────────
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
    if video:
        state.recommended_content = {
            "video_id": video.get("content_id") or video.get("video_id"),
            "title": video.get("title", ""),
            "url": video.get("url", ""),
            "thumbnail": video.get("thumbnail", ""),
            "reason": reason,
            "search_query": search_query,
            "candidate_pool": candidate_pool,
            "selected_score": selected_score
        }
    else:
        state.recommended_content = {
            "search_query": search_query,
            "reason": reason,
        }

    return state
