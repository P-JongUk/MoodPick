"""
ai/tools/emotion_record.py

Saves emotion analysis results to the database after each Counselor response.
Uses the emotion_records table created in migration 006.
"""

from supabase import create_client, Client

from ai.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY


def _get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def save_emotion_record(
    user_id: str,
    session_id: str,
    emotion: str,
    intensity: float,
    raw_message: str | None = None,
) -> dict:
    """
    Persist an emotion analysis result to the emotion_records table.

    Args:
        user_id:     The authenticated user's UUID.
        session_id:  The current counseling session UUID.
        emotion:     Detected emotion label (e.g. "불안", "슬픔", "스트레스").
        intensity:   Emotion intensity, 0.0–1.0.
        raw_message: Optional — original user message for future analysis.

    Returns:
        {"success": True, "id": "<uuid of inserted row>"}
        or {"success": False, "error": "<message>"} on failure.

    Notes:
        - Errors are caught and returned as {"success": False} rather than raised,
          so a save failure does not interrupt the counseling response pipeline.
        - Requires migration 006 to be applied (emotion_records table).
    """
    # Clamp intensity to valid range
    intensity = max(0.0, min(1.0, float(intensity)))

    try:
        supabase = _get_supabase()
        result = (
            supabase.table("emotion_records")
            .insert({
                "user_id": user_id,
                "session_id": session_id,
                "emotion": emotion,
                "intensity": intensity,
                "raw_message": raw_message,
            })
            .execute()
        )
        inserted = result.data[0] if result.data else {}
        return {"success": True, "id": inserted.get("id")}

    except Exception as e:
        # Non-fatal: log and continue
        return {"success": False, "error": str(e)}
