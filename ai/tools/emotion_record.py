"""
ai/tools/emotion_record.py

Saves emotion analysis results to the database after each Counselor response.
Uses the emotion_records table created in migration 006.
"""

import logging

from supabase import create_client, Client

from ai.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from ai.tools.emotion_va_map import get_nearest_emotion


logger = logging.getLogger(__name__)


def _get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def save_emotion_record(
    user_id: str,
    session_id: str,
    valence: float,
    arousal: float,
    emotion_description: str = "",
    raw_message: str | None = None,
) -> dict:
    """
    Persist an emotion analysis result to the emotion_records table.

    Args:
        user_id:             The authenticated user's UUID.
        session_id:          The current counseling session UUID.
        valence:             Valence score (-1.0 to 1.0).
        arousal:             Arousal score (-1.0 to 1.0).
        emotion_description: 1–2 sentence contextual description of the user's emotional state.
                             Used directly as the embedding query for content recommendation.
        raw_message:         Optional — original user message for future analysis.

    Returns:
        {"success": True, "id": "<uuid of inserted row>"}
        or {"success": False, "error": "<message>"} on failure.

    Notes:
        - Errors are caught and returned as {"success": False} rather than raised,
          so a save failure does not interrupt the counseling response pipeline.
        - Requires migrations 006 and 007 to be applied (emotion_records table + VA columns).
        - The closest discrete emotion label is calculated dynamically based on the VA coordinates.
    """
    try:
        supabase = _get_supabase()

        emotion, va_radius = get_nearest_emotion(valence, arousal)

        result = (
            supabase.table("emotion_records")
            .insert({
                "user_id": user_id,
                "session_id": session_id,
                "emotion": emotion,
                "emotion_description": emotion_description,
                "valence": valence,
                "arousal": arousal,
                "va_radius": va_radius,
                "raw_message": raw_message,
            })
            .execute()
        )
        inserted = result.data[0] if result.data else {}
        return {"success": True, "id": inserted.get("id")}

    except Exception as e:
        # Non-fatal: log and continue
        logger.warning("save_emotion_record failed error_type=%s", type(e).__name__)
        return {"success": False, "error": "emotion_record_save_failed"}
