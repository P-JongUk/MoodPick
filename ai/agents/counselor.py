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

from openai import OpenAI

from ai.config import OPENAI_API_KEY
from ai.state import CounselingState
from ai.utils import load_prompt
from ai.tools.rag_search import search_rag_context
from ai.tools.user_profile import get_user_profile
from ai.tools.emotion_record import save_emotion_record

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
                    "emotion": {
                        "type": "string",
                        "description": "감지된 상세 감정 (예: 단순 슬픔이 아닌 '과도한 자책감이 동반된 우울', '깊은 상실감' 등 구체적 묘사)",
                    },
                    "intensity": {
                        "type": "number",
                        "description": "감정 강도 (0.0~1.0). 매뉴얼 기준이 있다면 우선 적용.",
                    },
                },
                "required": ["user_id", "session_id", "emotion", "intensity"],
            },
        },
    },
]

# ── Tool dispatcher ─────────────────────────────────────────────────────────

_TOOL_FUNCTIONS = {
    "search_rag_context": lambda args: search_rag_context(
        query_text=args["query_text"],
        top_k=args.get("top_k", 3),
    ),
    "get_user_profile": lambda args: get_user_profile(
        user_id=args["user_id"],
    ),
    "save_emotion_record": lambda args: save_emotion_record(
        user_id=args["user_id"],
        session_id=args["session_id"],
        emotion=args["emotion"],
        intensity=args["intensity"],
    ),
}


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


def _execute_tool_call(tool_call) -> str:
    """Execute a single tool call and return the result as a JSON string."""
    fn_name = tool_call.function.name
    fn_args = json.loads(tool_call.function.arguments)

    executor = _TOOL_FUNCTIONS.get(fn_name)
    if not executor:
        return json.dumps({"error": f"Unknown tool: {fn_name}"})

    try:
        result = executor(fn_args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


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
            result_str = _execute_tool_call(tool_call)

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
                try:
                    args = json.loads(tool_call.function.arguments)
                    state.emotion_score = {
                        "emotion": args.get("emotion", ""),
                        "intensity": args.get("intensity", 0.0),
                    }
                except (json.JSONDecodeError, TypeError):
                    pass

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })

    # ── Extract final response ──────────────────────────────────────────
    final_content = response.choices[0].message.content or ""
    state.response = final_content

    # Check if counselor suggests recommendation in the response
    recommendation_signals = ["추천해드릴까요", "추천해 드릴까요", "들려드릴까요", "틀어드릴까요"]
    if any(signal in final_content for signal in recommendation_signals):
        state.needs_recommendation = True

    return state
