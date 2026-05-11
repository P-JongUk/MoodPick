"""
ai/agents/summarizer.py

오래된 상담 대화를 압축 요약하는 단발 LLM 호출 에이전트.
counselor.py와 동일한 OpenAI 클라이언트/모델 패턴을 따른다.
"""

import logging
import time

from openai import OpenAI

from ai.config import OPENAI_API_KEY
from ai.utils import load_prompt


logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"


def _get_openai() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env.local")
    return OpenAI(api_key=OPENAI_API_KEY)


def _format_messages_for_summary(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        speaker = "사용자" if role == "user" else "상담사"
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def summarize_conversation(
    messages: list[dict],
    previous_summary: str | None = None,
) -> str:
    """오래된 메시지들과 (있다면) 이전 요약을 입력받아 통합 요약을 생성한다."""
    if not messages:
        return previous_summary or ""

    client = _get_openai()
    system_prompt = load_prompt("summary_prompt.md")

    user_blocks = []
    if previous_summary:
        user_blocks.append(f"### 이전 요약\n{previous_summary.strip()}")
    user_blocks.append(
        "### 새로 추가된 대화\n" + _format_messages_for_summary(messages)
    )
    user_blocks.append(
        "위 내용을 바탕으로 통합 요약을 작성하세요. 본문만 출력합니다."
    )
    user_content = "\n\n".join(user_blocks)

    _t = time.perf_counter()
    response = client.chat.completions.create(
        model=_MODEL,
        temperature=0.3,
        max_tokens=600,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    logger.info(
        "[PERF] summarizer.llm=%.3fs msgs=%d had_prev=%s",
        time.perf_counter() - _t,
        len(messages),
        bool(previous_summary),
    )

    summary = (response.choices[0].message.content or "").strip()
    return summary or (previous_summary or "")
