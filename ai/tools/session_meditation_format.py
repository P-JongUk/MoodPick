"""counseling_sessions.meditation_audio_format 읽기/쓰기 (서비스 롤)."""

from __future__ import annotations

from ai.tools.content_history import _get_supabase

_VALID = frozenset({"guided", "music_only"})


def get_session_meditation_audio_format(session_id: str) -> str | None:
    try:
        supabase = _get_supabase()
        res = (
            supabase.table("counseling_sessions")
            .select("meditation_audio_format")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        v = res.data[0].get("meditation_audio_format")
        return v if v in _VALID else None
    except Exception:
        return None


def set_session_meditation_audio_format(session_id: str, value: str) -> None:
    if value not in _VALID:
        raise ValueError("meditation_audio_format must be 'guided' or 'music_only'")
    supabase = _get_supabase()
    supabase.table("counseling_sessions").update({"meditation_audio_format": value}).eq(
        "id", session_id
    ).execute()
