"""
ai/agents/orchestrator.py

Routes user messages by detecting crisis signals, classifying intent,
and determining whether content recommendation is needed.

Input:  state.message + 최근 history 슬라이스 (직전 어시스턴트 추천 제안 → 사용자 동의/거절 등 multi-turn 맥락 판정용)
Output: state.is_crisis, state.intent, state.needs_recommendation
"""

import json

from openai import OpenAI

from ai.config import OPENAI_API_KEY
from ai.state import CounselingState
from ai.utils import load_prompt

_MODEL = "gpt-4o-mini"
_HISTORY_TURNS = 4          # 직전 2턴분 (user/assistant 쌍 2개)
_HISTORY_CHAR_LIMIT = 400   # 추천 제안 의문형은 응답 끝부분에 위치 → 뒤에서 자르기


def _get_openai() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env.local")
    return OpenAI(api_key=OPENAI_API_KEY)


def _truncate_tail(text: str, limit: int) -> str:
    if not text or len(text) <= limit:
        return text
    return text[-limit:]


async def orchestrator_agent(state: CounselingState) -> CounselingState:
    """
    Classify a user message into crisis/intent/recommendation flags using
    recent conversation history as context.
    Returns the updated state.
    """
    system_prompt = load_prompt("orchestrator_prompt.md")

    history_msgs: list[dict] = []
    for msg in (state.messages or [])[-_HISTORY_TURNS:]:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        history_msgs.append({
            "role": role,
            "content": _truncate_tail(msg.get("content") or "", _HISTORY_CHAR_LIMIT),
        })

    client = _get_openai()
    response = client.chat.completions.create(
        model=_MODEL,
        temperature=0,
        max_tokens=100,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            *history_msgs,
            {"role": "user", "content": state.message},
        ],
    )

    raw = response.choices[0].message.content or "{}"
    result = json.loads(raw)

    state.is_crisis = bool(result.get("is_crisis", False))
    state.intent = result.get("intent", "상담")
    state.needs_recommendation = bool(result.get("needs_recommendation", False))

    # Safety: crisis overrides recommendation
    if state.is_crisis:
        state.needs_recommendation = False

    return state
