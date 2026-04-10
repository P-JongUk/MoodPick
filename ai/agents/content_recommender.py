"""
ai/agents/content_recommender.py

Generates a personalized YouTube search query based on the user's
emotional state, preferences, and content history.

Current scope:
  - Reads user_profile from state (cached by Counselor) or fetches if missing
  - Fetches content history (watched/liked/disliked)
  - Generates search query via GPT with template prompt
  - TODO: Call FastMCP YouTube server with the generated query (Phase 4)

Input:  state.emotion_score, state.user_profile
Output: state.recommended_content
"""

import json

from openai import OpenAI

from ai.config import OPENAI_API_KEY
from ai.state import CounselingState
from ai.utils import load_prompt
from ai.tools.content_history import get_content_history
from ai.tools.user_profile import get_user_profile

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

    # ── 5. TODO: MCP YouTube 서버 호출 (Phase 4에서 구현) ───────────────
    # from fastmcp import Client as MCPClient
    # async with MCPClient("mcp_servers/youtube/server.py") as mcp:
    #     videos = await mcp.call_tool(
    #         "search_youtube",
    #         {"query": search_query, "watched_ids": watched_ids, "max_results": 5},
    #     )
    # 현재는 쿼리만 저장하고 MCP 연동은 Phase 4에서 추가

    # ── 6. Store result ─────────────────────────────────────────────────
    state.recommended_content = {
        "search_query": search_query,
        "reason": reason,
        "watched_ids_excluded": len(watched_ids),
    }

    return state
