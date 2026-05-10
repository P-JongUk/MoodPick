"""
backend/app/services/session_summary.py

상담 멀티턴 대화의 토큰 누적을 막기 위한 하이브리드 컨텍스트 빌더.

- 메시지 수가 SUMMARY_TRIGGER_THRESHOLD 이하 → 전체 원문 그대로 전달
- 임계치 초과 → 가장 최근 RECENT_MESSAGES_KEEP건만 원문 유지,
  그 이전 메시지들은 counseling_sessions.summary 컬럼에 누적 요약으로 압축
- 매 턴 재요약은 비용이 크므로, 기존 요약 이후 새로 쌓인 메시지가
  SUMMARY_REFRESH_STEP건 미만이면 재요약을 미루고 그 사이 메시지를 원문으로 전달
"""

import logging

from supabase import Client

from ai.agents.summarizer import summarize_conversation


logger = logging.getLogger(__name__)


# 6턴(=12 메시지) 원문 보존, 16건 초과 시 요약 발동
RECENT_MESSAGES_KEEP = 12
SUMMARY_TRIGGER_THRESHOLD = 16
# 기존 요약 이후 새로 쌓인 메시지가 이 개수 미만이면 재요약을 미루고
# 그 사이 메시지를 원문으로 같이 전달한다 (매 턴 LLM 호출 방지).
SUMMARY_REFRESH_STEP = 4


def _short_id(value: str | None) -> str:
    return value[:8] if value else "-"


def _fetch_session_summary(supabase: Client, session_id: str) -> tuple[str | None, str | None]:
    """counseling_sessions에서 (summary, summary_until_created_at)을 조회."""
    result = (
        supabase.table("counseling_sessions")
        .select("summary, summary_until_created_at")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None, None
    row = result.data[0]
    return row.get("summary"), row.get("summary_until_created_at")


def _fetch_all_messages(supabase: Client, session_id: str) -> list[dict]:
    """role, content, created_at을 시간순으로 전체 조회."""
    result = (
        supabase.table("counseling_history")
        .select("role, content, created_at")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    return list(result.data or [])


def _strip_metadata(messages: list[dict]) -> list[dict]:
    """LLM에 전달할 형태(role, content)만 남긴다."""
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def _update_session_summary(
    supabase: Client,
    session_id: str,
    summary: str,
    summary_until_created_at: str,
) -> None:
    supabase.table("counseling_sessions").update(
        {
            "summary": summary,
            "summary_until_created_at": summary_until_created_at,
        }
    ).eq("id", session_id).execute()


def prepare_session_context(
    supabase: Client,
    session_id: str,
) -> tuple[str | None, list[dict]]:
    """현재 턴에 사용할 (summary, recent_messages)를 반환한다.

    - 짧은 세션: (None, 전체 메시지)
    - 긴 세션: (요약 본문, 최근 RECENT_MESSAGES_KEEP건)
    필요 시 counseling_sessions.summary를 갱신한다.
    """
    all_messages = _fetch_all_messages(supabase, session_id)

    if len(all_messages) <= SUMMARY_TRIGGER_THRESHOLD:
        return None, _strip_metadata(all_messages)

    to_summarize = all_messages[:-RECENT_MESSAGES_KEEP]
    recent = all_messages[-RECENT_MESSAGES_KEEP:]

    new_until = to_summarize[-1]["created_at"]
    prev_summary, prev_until = _fetch_session_summary(supabase, session_id)

    if prev_summary and prev_until == new_until:
        # 이전 요약이 이미 같은 범위를 커버 — LLM 호출 생략
        logger.info(
            "[summary] reuse session_id=%s msgs=%d",
            _short_id(session_id),
            len(to_summarize),
        )
        return prev_summary, _strip_metadata(recent)

    # 청크 배치: 기존 요약 이후 새로 쌓인 메시지가 SUMMARY_REFRESH_STEP 미만이면
    # 재요약을 미루고, 기존 요약 + 그 이후 메시지를 모두 원문으로 전달한다.
    if prev_summary and prev_until:
        uncovered = [m for m in all_messages if m["created_at"] > prev_until]
        new_to_summarize = [m for m in to_summarize if m["created_at"] > prev_until]
        if len(new_to_summarize) < SUMMARY_REFRESH_STEP:
            logger.info(
                "[summary] defer session_id=%s pending=%d step=%d",
                _short_id(session_id),
                len(new_to_summarize),
                SUMMARY_REFRESH_STEP,
            )
            return prev_summary, _strip_metadata(uncovered)

    try:
        new_summary = summarize_conversation(
            messages=_strip_metadata(to_summarize),
            previous_summary=prev_summary,
        )
        if new_summary:
            _update_session_summary(supabase, session_id, new_summary, new_until)
            logger.info(
                "[summary] updated session_id=%s msgs=%d incremental=%s",
                _short_id(session_id),
                len(to_summarize),
                bool(prev_summary),
            )
            return new_summary, _strip_metadata(recent)
    except Exception as e:
        logger.warning(
            "[summary] failed session_id=%s error_type=%s — falling back",
            _short_id(session_id),
            type(e).__name__,
        )

    # 폴백: 기존 요약이 있으면 그것을 사용하되, 그 요약이 커버하지 못하는
    # 최근 메시지(prev_until 이후)는 전부 원문으로 함께 전달해 누락을 막는다.
    # 기존 요약도 없다면 전체 원문을 전달 (요약 도입 전 동작과 동일).
    if prev_summary and prev_until:
        uncovered = [m for m in all_messages if m["created_at"] > prev_until]
        return prev_summary, _strip_metadata(uncovered or recent)
    return None, _strip_metadata(all_messages)
