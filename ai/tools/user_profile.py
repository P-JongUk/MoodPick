"""
ai/tools/user_profile.py

Fetches onboarding profile and recent emotion history for a user.
The result is cached in CounselingState.user_profile to avoid repeated DB calls.
"""

from supabase import create_client, Client

from ai.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# Number of recent survey_responses to include for emotion trend context
_RECENT_SESSIONS_LIMIT = 5


def _get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_user_profile(user_id: str) -> dict:
    """
    Fetch onboarding profile and recent emotion history for a user.

    Returns:
        {
            "display_name": "홍길동",
            "concerns": ["직장", "관계"],        # from onboarding_profile
            "comfort_style": ["음악"],           # from onboarding_profile
            "recent_emotions": [                 # from survey_responses (pre-session mood)
                {"emoji_value": "low", "score": 0.3, "created_at": "..."},
                ...
            ]
        }

    Notes:
        - onboarding_profile is a JSONB column added in migration 006.
        - If the column is not yet populated, concerns and comfort_style will be empty lists.
        - recent_emotions are taken from survey_responses WHERE phase='pre'.
    """
    supabase = _get_supabase()

    # ── 1. Fetch user_profiles row ─────────────────────────────────────────
    profile_res = (
        supabase.table("user_profiles")
        .select("display_name, onboarding_profile")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    profile_row = profile_res.data[0] if profile_res.data else {}
    onboarding = profile_row.get("onboarding_profile") or {}

    # ── 2. Fetch recent pre-session mood scores ────────────────────────────
    # Join via counseling_sessions to filter by user_id
    # survey_responses does not have user_id directly — we go through sessions.
    sessions_res = (
        supabase.table("counseling_sessions")
        .select("id")
        .eq("user_id", user_id)
        .order("started_at", desc=True)
        .limit(_RECENT_SESSIONS_LIMIT)
        .execute()
    )

    session_ids = [row["id"] for row in (sessions_res.data or [])]
    recent_emotions: list[dict] = []

    if session_ids:
        survey_res = (
            supabase.table("survey_responses")
            .select("emoji_value, score, created_at")
            .in_("session_id", session_ids)
            .eq("phase", "pre")
            .eq("question_key", "mood_general")
            .order("created_at", desc=True)
            .limit(_RECENT_SESSIONS_LIMIT)
            .execute()
        )
        recent_emotions = survey_res.data or []

    return {
        "display_name": profile_row.get("display_name", ""),
        "concerns": onboarding.get("concerns", []),
        "comfort_style": onboarding.get("comfort_style", []),
        "recent_emotions": recent_emotions,
    }
