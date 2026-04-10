"""
ai/agents/orchestrator.py

Routes user messages by detecting crisis signals, classifying intent,
and determining whether content recommendation is needed.

Input:  state.message (current user message only — no history needed)
Output: state.is_crisis, state.intent, state.needs_recommendation
"""

import json

from openai import OpenAI

from ai.config import OPENAI_API_KEY
from ai.state import CounselingState
from ai.utils import load_prompt

_MODEL = "gpt-4o-mini"


def _get_openai() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env.local")
    return OpenAI(api_key=OPENAI_API_KEY)


async def orchestrator_agent(state: CounselingState) -> CounselingState:
    """
    Classify a single user message into crisis/intent/recommendation flags.
    Returns the updated state.
    """
    system_prompt = load_prompt("orchestrator_prompt.md")

    client = _get_openai()
    response = client.chat.completions.create(
        model=_MODEL,
        temperature=0,
        max_tokens=100,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
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
