"""
ai/agents/counselor.py

Empathetic counseling agent with GPT Function Calling.

Available tools:
  - search_rag_context: RAG vector search for professional counseling knowledge
  - get_user_profile:   Onboarding profile + recent emotion history
  - save_emotion_record: Persist detected emotion to DB

Flow:
  1. Build messages (system prompt + history + current message)
  2. Send to GPT with tool definitions
  3. Loop: if GPT requests tool calls → execute → feed results back → re-call
  4. Extract final response + emotion analysis from GPT output
"""

import json
import logging

from openai import OpenAI

from ai.config import OPENAI_API_KEY
from ai.state import CounselingState
from ai.utils import load_prompt
from ai.tools.rag_search import search_rag_context
from ai.tools.user_profile import get_user_profile
from ai.tools.emotion_record import save_emotion_record
from ai.tools.emotion_va_map import get_nearest_emotion


logger = logging.getLogger(__name__)


def _short_id(value: str | None) -> str:
    return value[:8] if value else "-"


def _build_emotion_score(args: dict) -> dict:
    """save_emotion_record 인자에서 후속 에이전트들이 쓰는 통합 emotion_score를 만든다."""
    valence = float(args.get("valence", 0.0))
    arousal = float(args.get("arousal", 0.0))
    emotion_label, _ = get_nearest_emotion(valence, arousal)
    intensity = min(1.0, max(0.0, -valence) * 0.6 + abs(arousal) * 0.4)
    return {
        "valence": valence,
        "arousal": arousal,
        "emotion_description": args.get("emotion_description", ""),
        "emotion": emotion_label,
        "intensity": intensity,
    }

_MODEL = "gpt-4o-mini"

# ── OpenAI Function Calling tool definitions ────────────────────────────────

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_rag_context",
            "description": "RAG 벡터 검색으로 심리 상담 관련 전문 지식을 조회한다. 사용자의 고민에 맞는 상담 기법이나 정보가 필요할 때 호출한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_text": {
                        "type": "string",
                        "description": "검색할 쿼리 텍스트 (사용자 메시지 또는 핵심 키워드)",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "반환할 청크 수 (기본값: 3)",
                        "default": 3,
                    },
                },
                "required": ["query_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "사용자의 온보딩 프로필(고민 카테고리, 선호 위로 방식)과 최근 감정 이력을 조회한다. 첫 응답 시 호출하여 개인화된 상담을 제공한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "사용자 UUID",
                    },
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_emotion_record",
            "description": "사용자 메시지에서 감지한 감정 분석 결과를 DB에 저장한다. 응답 생성 후 반드시 호출한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "사용자 UUID",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "현재 상담 세션 UUID",
                    },
                    "valence": {
                        "type": "number",
                        "description": "감정의 긍정/부정 정도 (-1.0 매우 부정 ~ 1.0 매우 긍정). 연속적인 실수값으로 평가.",
                    },
                    "arousal": {
                        "type": "number",
                        "description": "감정의 각성/활성화 정도 (-1.0 매우 침잠 ~ 1.0 매우 활성화). 연속적인 실수값으로 평가.",
                    },
                    "emotion_description": {
                        "type": "string",
                        "description": "사용자의 현재 감정 상태를 1~2문장으로 서술. 단순 레이블이 아닌 맥락·원인·필요를 포함할 것. 예: '직장 스트레스와 자책감으로 지쳐 있으며, 조용히 마음을 달래줄 콘텐츠가 필요한 상태' 이 문장은 콘텐츠 추천 임베딩 쿼리로 직접 사용됨.",
                    },
                },
                "required": ["user_id", "session_id", "valence", "arousal", "emotion_description"],
            },
        },
    },
]

# ── Tool dispatcher ─────────────────────────────────────────────────────────

def _execute_tool_call(tool_call, state: CounselingState) -> str:
    """Execute a single tool call and return the result as a JSON string."""
    fn_name = tool_call.function.name
    fn_args = json.loads(tool_call.function.arguments)

    logger.info(
        "AI tool call fn=%s user_id=%s session_id=%s arg_keys=%s",
        fn_name,
        _short_id(state.user_id),
        _short_id(state.session_id),
        sorted(fn_args.keys()),
    )

    if fn_name == "search_rag_context":
        result = search_rag_context(
            query_text=fn_args["query_text"],
            top_k=fn_args.get("top_k", 3),
        )
    elif fn_name == "get_user_profile":
        result = get_user_profile(
            user_id=fn_args["user_id"],
        )
    elif fn_name == "save_emotion_record":
        result = save_emotion_record(
            user_id=fn_args["user_id"],
            session_id=fn_args["session_id"],
            valence=fn_args.get("valence", 0.0),
            arousal=fn_args.get("arousal", 0.0),
            emotion_description=fn_args.get("emotion_description", ""),
            raw_message=state.message,  # 자동 주입
        )
    else:
        return json.dumps({"error": f"Unknown tool: {fn_name}"})

    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _get_openai() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env.local")
    return OpenAI(api_key=OPENAI_API_KEY)


def _build_system_message(state: CounselingState) -> str:
    """Build system prompt with injected context."""
    base_prompt = load_prompt("system_prompt.md")

    # Inject user_id and session_id so GPT can pass them to tools
    session_context = (
        f"\n\n### [Module 0: Session Context]\n"
        f"- user_id: {state.user_id}\n"
        f"- session_id: {state.session_id}\n"
    )

    return base_prompt + session_context



async def counselor_agent(state: CounselingState) -> CounselingState:
    """
    Generate an empathetic counseling response using GPT Function Calling.

    The model may call tools (RAG search, user profile, emotion record)
    as many times as it needs before producing the final text response.
    """
    client = _get_openai()

    # Build message list: system + history + current user message
    messages = [{"role": "system", "content": _build_system_message(state)}]

    # Append conversation history (multi-turn)
    for msg in state.messages:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Current user message
    messages.append({"role": "user", "content": state.message})

    # ── Function Calling loop ───────────────────────────────────────────
    max_iterations = 5  # safety limit to prevent infinite loops
    save_emotion_called = False  # track if save_emotion_record was invoked

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=_MODEL,
            temperature=0.7,
            max_tokens=500,
            tools=_TOOL_DEFINITIONS,
            messages=messages,
        )

        choice = response.choices[0]

        # If no tool calls, we have the final response
        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            break

        # Append assistant message with tool calls
        messages.append(choice.message)

        # Execute each tool call and append results
        for tool_call in choice.message.tool_calls:
            result_str = _execute_tool_call(tool_call, state)

            # Cache user_profile in state if fetched
            if tool_call.function.name == "get_user_profile":
                try:
                    profile_data = json.loads(result_str)
                    if "error" not in profile_data:
                        state.user_profile = profile_data
                except (json.JSONDecodeError, TypeError):
                    pass

            # Extract emotion_score from save_emotion_record call
            if tool_call.function.name == "save_emotion_record":
                save_emotion_called = True
                try:
                    args = json.loads(tool_call.function.arguments)
                    state.emotion_score = _build_emotion_score(args)
                except (json.JSONDecodeError, TypeError):
                    pass

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })

    # ── Extract final response ──────────────────────────────────────────
    # max_iterations에 도달했는데 마지막도 tool_calls인 경우 content가 비어 사용자에게
    # 빈 메시지가 전달될 수 있어 안전장치를 둔다.
    final_content = (response.choices[0].message.content or "").strip()
    if not final_content:
        final_content = "지금은 답변을 정리하기 어렵네요. 다시 한 번 말씀해 주실 수 있을까요?"
    state.response = final_content

    # ── Guarantee: save emotion even if GPT skipped the tool ────────────
    # When GPT replies with text immediately (no tool calls), emotion_records
    # would be missing. Force a single save_emotion_record call via tool_choice.
    if not save_emotion_called:
        try:
            forced = _get_openai().chat.completions.create(
                model=_MODEL,
                temperature=0.0,
                max_tokens=150,
                tools=_TOOL_DEFINITIONS,
                tool_choice={"type": "function", "function": {"name": "save_emotion_record"}},
                messages=messages,
            )
            for tc in (forced.choices[0].message.tool_calls or []):
                if tc.function.name == "save_emotion_record":
                    _execute_tool_call(tc, state)
                    try:
                        args = json.loads(tc.function.arguments)
                        state.emotion_score = _build_emotion_score(args)
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception as e:
            logger.warning(
                "Forced emotion save failed user_id=%s session_id=%s error_type=%s",
                _short_id(state.user_id),
                _short_id(state.session_id),
                type(e).__name__,
            )

    # Check if counselor suggests recommendation in the response
    recommendation_signals = ["추천해드릴까요", "추천해 드릴까요", "들려드릴까요", "틀어드릴까요"]
    if any(signal in final_content for signal in recommendation_signals):
        state.needs_recommendation = True

    return state
