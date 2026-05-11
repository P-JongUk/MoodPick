"""
명상·오디오 추천이 애매할 때(가이드 vs 음악만) 짧게 확인 질문을 붙이는 로직.

- 라우팅 트리거는 Orchestrator의 `content_format == "audio"`로 결정
- 클라리피 답변 파싱은 명시적 키워드("가이드"/"음악만"/숫자 등)에만 매칭
- 답이 모호하면 None 반환 → 호출 측이 "새 요청"으로 해석하고 일반 추천 진행
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from ai.meditation_audio_signals import (
    explicit_wants_guided,
    is_audio_content,
    wants_music_only_bgm,
)
from ai.state import CounselingState

MEDITATION_FORMAT_CLARIFY_MARKER = "어떤 형태가 더 편하실까요"

MEDITATION_FORMAT_CLARIFICATION = (
    "\n\n어떤 형태가 더 편하실까요? "
    "말 없는 음악·배경음만 원하시면 **「음악만」**이라고, "
    "호흡·안내에 맞춰 따라 하실 수 있는 **가이드형**을 원하시면 **「가이드」**라고 짧게 답해 주세요. "
    "답이 없거나 모호하면 **가이드형**(말로 안내하는 오디오)으로 맞출게요."
)

# 새 콘텐츠 요청을 식별하기 위한 명사구 패턴 (영상·노래·드라마·게임 등)
_NEW_REQUEST_NOUN_RE = re.compile(
    r"[가-힣A-Za-z0-9]{2,}\s*"
    r"(영상|뮤비|풀영상|예능|클립|편|쇼|짤|하이라이트|노래|곡|플레이리스트|playlist|드라마|영화|게임|실황)"
)


def _looks_like_new_request(user_message: str | None) -> bool:
    """직전 클라리피 메시지에 대한 답변이 아닌, 명백한 새 요청으로 보이는지."""
    if not user_message:
        return False
    raw = user_message.strip()
    if not raw:
        return False
    # 명확한 클라리피 답변이면 새 요청 아님
    if parse_meditation_format_reply(raw) is not None:
        return False
    # 단답이 아니면 새 요청
    if len(raw) > 12:
        return True
    # 콘텐츠 명사구가 등장하면 새 요청
    if _NEW_REQUEST_NOUN_RE.search(raw):
        return True
    return False


def is_reply_to_meditation_format_clarification(
    messages: list[dict], user_message: str | None
) -> bool:
    if not messages or not user_message:
        return False
    last = messages[-1]
    if last.get("role") != "assistant":
        return False
    if MEDITATION_FORMAT_CLARIFY_MARKER not in (last.get("content") or ""):
        return False
    if _looks_like_new_request(user_message):
        return False
    return True


def parse_meditation_format_reply(message: str | None) -> Optional[Literal["guided", "music_only"]]:
    """명확할 때만 반환. None 이면 호출 측에서 새 요청으로 처리."""
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
    """세션에 저장된 명상 포맷 선호를 이번 요청에 적용할지.

    LLM이 이번 메시지를 audio로 분류한 경우에만 적용한다. video/music/unspecified면
    이전 세션 선호는 무시.
    """
    if not state.meditation_audio_format:
        return False
    return is_audio_content(state.content_format)


def should_ask_meditation_format_clarification(state: CounselingState) -> bool:
    """audio 의도이고 가이드/음악만 신호가 아직 없을 때만 확인 질문."""
    if not state.needs_recommendation:
        return False
    if state.meditation_audio_format:
        return False
    if not is_audio_content(state.content_format):
        return False
    msg = state.message
    if wants_music_only_bgm(msg):
        return False
    if explicit_wants_guided(msg):
        return False
    return True
