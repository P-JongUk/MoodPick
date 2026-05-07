"""
ai/tools/content_history.py

Fetches a user's watched content and feedback records.
Used by the Content Recommender Agent to:
  - Exclude already-watched videos from MCP search results
  - Inform final video selection with like/dislike signals
"""

from supabase import create_client, Client

from ai.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# Cap the history window to avoid overly large payloads
_WATCHED_LIMIT = 50
_FEEDBACK_LIMIT = 100


def _get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_content_history(user_id: str) -> dict:
    """
    Return the user's content viewing and feedback history.

    Returns:
        {
            "watched_ids": ["videoId1", "videoId2", ...],   # content_id values
            "liked_ids":   ["videoId3", ...],               # feedback = 'like'
            "disliked_ids": ["videoId4", ...],              # feedback = 'dislike'
        }

    Notes:
        - content_id in watched_content_records and content_feedback
          corresponds to the YouTube video ID.
        - watched_ids is used to exclude already-seen videos in the MCP search.
        - liked_ids / disliked_ids guide the final video selection by the agent.
    """
    supabase = _get_supabase()

    # ── 1. Watched content ─────────────────────────────────────────────────
    watched_res = (
        supabase.table("watched_content_records")
        .select("content_id")
        .eq("user_id", user_id)
        .order("watched_at", desc=True)
        .limit(_WATCHED_LIMIT)
        .execute()
    )
    watched_ids = [row["content_id"] for row in (watched_res.data or [])]

    # ── 2. Content feedback ────────────────────────────────────────────────
    feedback_res = (
        supabase.table("content_feedback")
        .select("content_id, feedback")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(_FEEDBACK_LIMIT)
        .execute()
    )
    feedback_rows = feedback_res.data or []

    liked_ids = [r["content_id"] for r in feedback_rows if r["feedback"] == "like"]
    disliked_ids = [r["content_id"] for r in feedback_rows if r["feedback"] == "dislike"]

    return {
        "watched_ids": watched_ids,
        "liked_ids": liked_ids,
        "disliked_ids": disliked_ids,
    }
