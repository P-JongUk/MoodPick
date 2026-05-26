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

import asyncio
import dataclasses
import json
import logging
import time
from typing import AsyncGenerator

from ai.clients import get_openai
from ai.state import CounselingState
from ai.utils import load_prompt
from ai.tools.rag_search import search_rag_context
from ai.tools.user_profile import get_user_profile
from ai.tools.emotion_record import save_emotion_record
from ai.tools.emotion_va_map import get_nearest_emotion
from ai.tools.preference_map import counseling_tone_guidance, counselor_persona_guidance


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _FunctionLike:
    name: str
    arguments: str


@dataclasses.dataclass
class _ToolCallLike:
    """Minimal duck-type of OpenAI's tool_call object, built from streaming chunks."""
    id: str
    function: _FunctionLike


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
            "description": "사용자의 온보딩 프로필(고민 카테고리, 선호 위로 방식)과 최근 감정 이력을 조회한다. 첫 응답 시 1회 호출. 결과의 concerns는 사용자가 현재 발화에서 구체적 주제를 명시하지 않은 경우에만 부드러운 화두 열기 단서로 활용하고, 사용자가 다른 주제를 꺼냈다면 무시한다. concerns 라벨은 사용자에게 직접 노출하지 않는다.",
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

async def _execute_tool_call(tool_call: "_ToolCallLike | object", state: CounselingState) -> str:
    """Execute a single tool call and return the result as a JSON string.

    동기 도구(Supabase/OpenAI sync SDK)는 asyncio.to_thread로 감싸 이벤트 루프를 막지 않는다.
    """
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
        result = await asyncio.to_thread(
            search_rag_context,
            query_text=fn_args["query_text"],
            top_k=fn_args.get("top_k", 3),
        )
    elif fn_name == "get_user_profile":
        result = await asyncio.to_thread(
            get_user_profile,
            user_id=fn_args["user_id"],
        )
    elif fn_name == "save_emotion_record":
        result = await asyncio.to_thread(
            save_emotion_record,
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


def _build_system_message(state: CounselingState) -> str:
    """Build system prompt with injected context."""
    base_prompt = load_prompt("system_prompt.md")

    # 세션의 persona를 Module 1 위치에 주입 — system_prompt.md의 {{persona_block}} 치환
    base_prompt = base_prompt.replace(
        "{{persona_block}}", counselor_persona_guidance(state.persona)
    )

    # 사용자 프로필 캐시가 없으면 1회 동기 fetch — GPT 도구 호출 의존성 없이
    # 매 턴 일관되게 톤 가이드를 시스템 메시지에 포함시키기 위함.
    profile = state.user_profile
    if not profile:
        try:
            profile = get_user_profile(state.user_id) or {}
            state.user_profile = profile
        except Exception as e:
            logger.warning(
                "Failed to prefetch user_profile for tone block user_id=%s error_type=%s",
                _short_id(state.user_id),
                type(e).__name__,
            )
            profile = {}

    # tone_block은 Module 1 바로 뒤(Module 1.5)에 placeholder로 주입되어
    # 페르소나 어조와 행동 가이드가 시각·구조적으로 인접하도록 한다.
    # counseling_tone_guidance는 빈 배열에서도 fallback 블록을 반환하므로 placeholder가 빈 줄로 남지 않는다.
    tone_block = counseling_tone_guidance(profile.get("counseling_tone", []) or [])
    base_prompt = base_prompt.replace("{{tone_block}}", tone_block)

    # Inject user_id and session_id so GPT can pass them to tools
    session_context = (
        f"\n\n### [Module 0: Session Context]\n"
        f"- user_id: {state.user_id}\n"
        f"- session_id: {state.session_id}\n"
    )

    # 임계치 초과 세션이라면 오래된 대화 요약을 주입한다.
    # state.messages에는 최근 N턴 원문만 들어있으므로, 그 이전 맥락은 이 블록으로 보존한다.
    summary_block = ""
    if state.session_summary:
        summary_block = (
            f"\n\n### [Module 0.5: Previous Conversation Summary]\n"
            f"이전 대화의 요약입니다. 사용자의 맥락 이해에 활용하되, "
            f"요약 자체를 사용자에게 직접 인용하거나 \"요약하면\"식으로 언급하지 마세요.\n"
            f"{state.session_summary}\n"
        )

    # orchestrator가 이 턴을 추천으로 라우팅했다면 counselor에게 "정보 요청 질문/추천 수반 질문 없이"
    # 평서문으로 마무리하라고 알려준다. 시스템이 직후에 추천 카드를 자동으로 덧붙이므로
    # 사용자에게 답을 요구하는 질문으로 끝내면 흐름이 어색해진다.
    routing_block = ""
    if state.needs_recommendation:
        routing_block = (
            "\n\n### [Module 0.7: Routing Context]\n"
            "이번 턴은 사용자가 이미 콘텐츠 추천을 명시적으로 요청했거나 "
            "Orchestrator가 추천이 필요하다고 판단한 턴입니다. 응답 직후 시스템이 "
            "자동으로 추천 콘텐츠를 덧붙입니다. 따라서 다음 규칙을 반드시 지키세요:\n"
            "- 응답을 \"어떤 느낌의 노래를 듣고 싶어?\" 같은 **정보 요청 질문**으로 끝내지 마십시오. "
            "사용자는 곧바로 추천을 받기를 기대합니다.\n"
            "- \"추천해 드릴까요?\", \"한 곡 골라 드릴까요?\" 같은 **추천 수반 질문**으로 끝내지 마십시오. "
            "추천은 이미 결정되어 있습니다.\n"
            "- 대신 1~2문장의 짧은 공감 후, \"마음에 맞는 곡을 한 번 찾아볼게.\" 같이 "
            "추천이 이어질 것을 자연스럽게 알리는 평서문으로 끝내십시오.\n"
            "- 페르소나 톤은 그대로 유지하십시오."
        )

    return base_prompt + session_context + summary_block + routing_block



async def counselor_agent(state: CounselingState) -> CounselingState:
    """
    Generate an empathetic counseling response using GPT Function Calling.

    The model may call tools (RAG search, user profile, emotion record)
    as many times as it needs before producing the final text response.
    """
    client = get_openai()

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

    for _round in range(max_iterations):
        _t = time.perf_counter()
        response = await client.chat.completions.create(
            model=_MODEL,
            temperature=0.7,
            max_tokens=500,
            tools=_TOOL_DEFINITIONS,
            messages=messages,
        )
        logger.info("[PERF] counselor.llm[%d]=%.3fs", _round, time.perf_counter() - _t)

        choice = response.choices[0]

        # If no tool calls, we have the final response
        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            break

        # Append assistant message with tool calls
        messages.append(choice.message)

        # Execute each tool call and append results
        for tool_call in choice.message.tool_calls:
            _t = time.perf_counter()
            result_str = await _execute_tool_call(tool_call, state)
            logger.info(
                "[PERF] counselor.tool[%s]=%.3fs",
                tool_call.function.name,
                time.perf_counter() - _t,
            )

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
            _t = time.perf_counter()
            forced = await get_openai().chat.completions.create(
                model=_MODEL,
                temperature=0.0,
                max_tokens=150,
                tools=_TOOL_DEFINITIONS,
                tool_choice={"type": "function", "function": {"name": "save_emotion_record"}},
                messages=messages,
            )
            logger.info("[PERF] counselor.forced_emotion_llm=%.3fs", time.perf_counter() - _t)
            for tc in (forced.choices[0].message.tool_calls or []):
                if tc.function.name == "save_emotion_record":
                    await _execute_tool_call(tc, state)
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

    return state


async def counselor_agent_stream(state: CounselingState) -> AsyncGenerator[str, None]:
    """
    counselor_agent의 스트리밍 버전.

    툴 호출 라운드: 청크에서 tool_calls 조각을 모아 실행 (텍스트 미출력)
    텍스트 생성 라운드: 청크에서 content가 도착하는 즉시 yield → 프론트엔드로 전송
    루프 종료 후 state.response, state.emotion_score 세팅 (기존과 동일)
    """
    client = get_openai()

    messages = [{"role": "system", "content": _build_system_message(state)}]
    for msg in state.messages:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": state.message})

    max_iterations = 5
    save_emotion_called = False

    for _round in range(max_iterations):
        _t = time.perf_counter()
        stream = await client.chat.completions.create(
            model=_MODEL,
            temperature=0.7,
            max_tokens=500,
            tools=_TOOL_DEFINITIONS,
            messages=messages,
            stream=True,
        )

        content_pieces: list[str] = []
        # index → {"id": str, "name": str, "arguments": str}
        tool_calls_acc: dict[int, dict] = {}
        finish_reason: str | None = None

        async for chunk in stream:
            choice = chunk.choices[0]
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = choice.delta

            if delta.content:
                content_pieces.append(delta.content)
                yield delta.content  # 텍스트 청크를 즉시 내보냄

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_acc[idx]["id"] += tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

        logger.info("[PERF] counselor_stream.llm[%d]=%.3fs", _round, time.perf_counter() - _t)

        # 텍스트 응답 완료 (툴 호출 없음)
        if finish_reason == "stop" or not tool_calls_acc:
            state.response = "".join(content_pieces).strip()
            if not state.response:
                state.response = "지금은 답변을 정리하기 어렵네요. 다시 한 번 말씀해 주실 수 있을까요?"
            break

        # 툴 호출 처리
        sorted_tcs = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
        assembled_tool_calls = [
            {"id": tc["id"], "type": "function",
             "function": {"name": tc["name"], "arguments": tc["arguments"]}}
            for tc in sorted_tcs
        ]

        messages.append({
            "role": "assistant",
            "content": "".join(content_pieces) or None,
            "tool_calls": assembled_tool_calls,
        })

        for tc_dict in assembled_tool_calls:
            tool_call_obj = _ToolCallLike(
                id=tc_dict["id"],
                function=_FunctionLike(
                    name=tc_dict["function"]["name"],
                    arguments=tc_dict["function"]["arguments"],
                ),
            )
            _t = time.perf_counter()
            result_str = await _execute_tool_call(tool_call_obj, state)
            logger.info(
                "[PERF] counselor_stream.tool[%s]=%.3fs",
                tc_dict["function"]["name"],
                time.perf_counter() - _t,
            )

            if tc_dict["function"]["name"] == "get_user_profile":
                try:
                    profile_data = json.loads(result_str)
                    if "error" not in profile_data:
                        state.user_profile = profile_data
                except (json.JSONDecodeError, TypeError):
                    pass

            if tc_dict["function"]["name"] == "save_emotion_record":
                save_emotion_called = True
                try:
                    args = json.loads(tc_dict["function"]["arguments"])
                    state.emotion_score = _build_emotion_score(args)
                except (json.JSONDecodeError, TypeError):
                    pass

            messages.append({
                "role": "tool",
                "tool_call_id": tc_dict["id"],
                "content": result_str,
            })

    # 감정 저장이 누락된 경우 강제 호출 (기존 counselor_agent와 동일)
    if not save_emotion_called:
        try:
            _t = time.perf_counter()
            forced = await get_openai().chat.completions.create(
                model=_MODEL,
                temperature=0.0,
                max_tokens=150,
                tools=_TOOL_DEFINITIONS,
                tool_choice={"type": "function", "function": {"name": "save_emotion_record"}},
                messages=messages,
            )
            logger.info("[PERF] counselor_stream.forced_emotion_llm=%.3fs", time.perf_counter() - _t)
            for tc in (forced.choices[0].message.tool_calls or []):
                if tc.function.name == "save_emotion_record":
                    await _execute_tool_call(tc, state)
                    try:
                        args = json.loads(tc.function.arguments)
                        state.emotion_score = _build_emotion_score(args)
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception as e:
            logger.warning(
                "Forced emotion save failed (stream) user_id=%s session_id=%s error_type=%s",
                _short_id(state.user_id),
                _short_id(state.session_id),
                type(e).__name__,
            )
