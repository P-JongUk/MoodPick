"""
ai/agents/orchestrator.py

Routes user messages by detecting crisis signals, classifying intent,
and determining whether content recommendation is needed.

Input:  state.message + 최근 history 슬라이스 (직전 어시스턴트 추천 제안 → 사용자 동의/거절 등 multi-turn 맥락 판정용)
Output: state.is_crisis, state.intent, state.needs_recommendation
"""

import json

from ai.clients import get_openai
from ai.state import CounselingState
from ai.utils import load_prompt

_MODEL = "gpt-4o-mini"
_HISTORY_TURNS = 4          # 직전 2턴분 (user/assistant 쌍 2개)
_HISTORY_CHAR_LIMIT = 400   # 추천 제안 의문형은 응답 끝부분에 위치 → 뒤에서 자르기


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

    client = get_openai()
    response = await client.chat.completions.create(
        model=_MODEL,
        temperature=0,
        max_tokens=200,
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
    state.is_off_topic = bool(result.get("is_off_topic", False))
    state.is_injection = bool(result.get("is_injection", False))
    state.intent = result.get("intent", "상담")
    state.needs_recommendation = bool(result.get("needs_recommendation", False))

    fmt = result.get("content_format", "unspecified")
    if fmt not in ("video", "music", "audio", "unspecified"):
        fmt = "unspecified"
    state.content_format = fmt

    hints = result.get("content_query_hints", [])
    if isinstance(hints, list):
        state.content_query_hints = [h for h in hints if isinstance(h, str) and h.strip()]
    else:
        state.content_query_hints = []

    # Safety: crisis overrides recommendation, off-topic, and injection
    if state.is_crisis:
        state.needs_recommendation = False
        state.is_off_topic = False
        state.is_injection = False

    # Off-topic 주제에는 추천도 불필요
    if state.is_off_topic:
        state.needs_recommendation = False

    # Injection/jailbreak 시도에는 추천 차단
    if state.is_injection:
        state.needs_recommendation = False

    return state
