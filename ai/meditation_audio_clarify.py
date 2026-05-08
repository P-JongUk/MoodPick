"""
명상·오디오 추천이 애매할 때(가이드 vs 음악만) 짧게 확인 질문을 붙이는 로직.

- 이전 assistant 메시지에 확인 문구가 있으면 사용자 답을 guided | music_only 로 파싱
- 답이 모호하면 기본값 guided (제품 정책)
"""

from __future__ import annotations

from typing import Literal, Optional

from ai.meditation_audio_signals import (
    explicit_wants_guided,
    wants_music_only_bgm,
    wants_podcast,
)
from ai.state import CounselingState

MEDITATION_FORMAT_CLARIFY_MARKER = "어떤 형태가 더 편하실까요"

MEDITATION_FORMAT_CLARIFICATION = (
    "\n\n어떤 형태가 더 편하실까요? "
    "말 없는 음악·배경음만 원하시면 **「음악만」**이라고, "
    "호흡·안내에 맞춰 따라 하실 수 있는 **가이드형**을 원하시면 **「가이드」**라고 짧게 답해 주세요. "
    "답이 없거나 모호하면 **가이드형**(말로 안내하는 오디오)으로 맞출게요."
)


def is_reply_to_meditation_format_clarification(
    messages: list[dict], user_message: str | None
) -> bool:
    if not messages or not user_message:
        return False
    last = messages[-1]
    if last.get("role") != "assistant":
        return False
    return MEDITATION_FORMAT_CLARIFY_MARKER in (last.get("content") or "")


def parse_meditation_format_reply(message: str | None) -> Optional[Literal["guided", "music_only"]]:
    """명확할 때만 반환. None 이면 호출 측에서 guided 기본값 적용."""
    if not message:
        return None
    raw = message.strip()
    m = raw.lower()

    if wants_music_only_bgm(raw):
        return "music_only"
    if explicit_wants_guided(raw):
        return "guided"

    if m in ("1", "①") or "1번" in m or "첫" in m:
        return "music_only"
    if m in ("2", "②") or "2번" in m or "두번째" in m or "둘째" in m:
        return "guided"

    if any(x in m for x in ("음악만", "music only", "bgm", "말 없", "인스트루멘탈", "instrumental")):
        return "music_only"

    if any(x in m for x in ("ㅇ", "y", "yes", "네", "응", "그래", "좋아", "ok")):
        if len(raw) <= 12:
            return "guided"

    return None


def meditation_audio_format_applies_to_current_message(state: CounselingState) -> bool:
    """세션에 저장된 선호를 이번 요청에 적용할지(명상·오디오 맥락일 때만)."""
    if not state.meditation_audio_format:
        return False
    msg = state.message
    return bool(
        wants_podcast(msg)
        or wants_music_only_bgm(msg)
        or explicit_wants_guided(msg)
    )


def should_ask_meditation_format_clarification(state: CounselingState) -> bool:
    if not state.needs_recommendation:
        return False
    if state.meditation_audio_format:
        return False
    msg = state.message
    if not wants_podcast(msg):
        return False
    if wants_music_only_bgm(msg):
        return False
    if explicit_wants_guided(msg):
        return False
    return True
