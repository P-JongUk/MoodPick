"""
ai/agents/content_recommender.py

Generates a personalized YouTube search query based on the user's
emotional state, preferences, and content history, then calls the
FastMCP YouTube server to fetch actual video results.

Input:  state.emotion_score, state.user_profile
Output: state.recommended_content
"""

import json
from pathlib import Path

from openai import OpenAI
from fastmcp import Client as MCPClient

from ai.config import OPENAI_API_KEY
from ai.state import CounselingState
from ai.utils import load_prompt
from ai.tools.content_history import get_content_history
from ai.tools.user_profile import get_user_profile

# MCP 서버 경로
_MCP_SERVER_PATH = str(Path(__file__).parent.parent.parent / "mcp_servers" / "server.py")

_MODEL = "gpt-4o-mini"


def _get_openai() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env.local")
    return OpenAI(api_key=OPENAI_API_KEY)


async def content_recommender_agent(state: CounselingState) -> CounselingState:
    """
    Generate a personalized YouTube search query and recommendation reason.

    Steps:
      1. Read user profile from state (or fetch if not cached)
      2. Fetch content history
      3. Build prompt with template substitution
      4. Call GPT to generate search_query + reason
      5. (TODO) Call MCP YouTube server with the query
      6. Store result in state.recommended_content
    """
    # ── 1. User profile (reuse from Counselor if available) ─────────────
    profile = state.user_profile
    if not profile:
        profile = get_user_profile(state.user_id)
        state.user_profile = profile

    concerns = ", ".join(profile.get("concerns", [])) or "없음"
    comfort_style = ", ".join(profile.get("comfort_style", [])) or "음악"

    # ── 2. Content history ──────────────────────────────────────────────
    history = get_content_history(state.user_id)
    watched_ids = history.get("watched_ids", [])

    # ── 3. Build prompt with template substitution ──────────────────────
    emotion = state.emotion_score.get("emotion", "스트레스")
    intensity = state.emotion_score.get("intensity", 0.5)

    prompt_template = load_prompt("content_recommender_prompt.md")
    user_prompt = prompt_template.format(
        emotion=emotion,
        intensity=intensity,
        concerns=concerns,
        comfort_style=comfort_style,
    )

    # ── 4. GPT call for query generation ────────────────────────────────
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
                    f"감정: {emotion} (강도: {intensity})\n"
                    f"고민: {concerns}\n"
                    f"위로 방식: {comfort_style}\n"
                    f"이미 본 영상 수: {len(watched_ids)}개"
                ),
            },
        ],
    )

    raw = response.choices[0].message.content or "{}"
    result = json.loads(raw)

    search_query = result.get("search_query", "healing music relaxing")
    reason = result.get("reason", "마음을 편안하게 해줄 콘텐츠를 추천드려요.")

    # ── 5. MCP YouTube 서버 호출 ──────────────────────────────────────────
    video = None
    try:
        async with MCPClient(_MCP_SERVER_PATH) as mcp:
            mcp_result = await mcp.call_tool(
                "search_youtube",
                {"query": search_query, "watched_ids": watched_ids, "max_results": 5},
            )
            videos = json.loads(mcp_result.content[0].text) if mcp_result.content else []

            # Filter out errored responses
            if videos and "error" not in videos[0]:
                video = videos[0]  # Pick the top result
    except Exception:
        # MCP 서버 미응답 시 추천 없이 상담만 반환
        video = None

    # ── 6. Store result ─────────────────────────────────────────────────
    if video:
        state.recommended_content = {
            "video_id": video["video_id"],
            "title": video["title"],
            "url": video["url"],
            "thumbnail": video.get("thumbnail", ""),
            "reason": reason,
        }
    else:
        state.recommended_content = {
            "search_query": search_query,
            "reason": reason,
        }

    return state
