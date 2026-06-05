from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from supabase import Client

from app.auth import CurrentUser, get_current_user, is_admin_user, require_admin
from app.services.supabase_service import get_supabase_client


router = APIRouter(prefix="/admin", tags=["admin"])


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_table_rows(
    supabase: Client,
    table: str,
    select: str = "*",
    *,
    limit: int = 5000,
    order_by: str | None = None,
    desc: bool = True,
    gte: tuple[str, str] | None = None,
) -> list[dict[str, Any]]:
    try:
        query = supabase.table(table).select(select)
        if gte:
            query = query.gte(gte[0], gte[1])
        if order_by:
            query = query.order(order_by, desc=desc)
        result = query.limit(limit).execute()
        return list(result.data or [])
    except Exception:
        return []


def _safe_count(supabase: Client, table: str, *, gte: tuple[str, str] | None = None) -> int:
    try:
        query = supabase.table(table).select("id", count="exact")
        if gte:
            query = query.gte(gte[0], gte[1])
        result = query.limit(1).execute()
        if result.count is not None:
            return int(result.count)
    except Exception:
        pass
    return len(_safe_table_rows(supabase, table, "id", limit=5000, gte=gte))


def _date_key(value: str | None) -> str | None:
    parsed = _parse_ts(value)
    return parsed.date().isoformat() if parsed else None


def _short_user_id(user_id: str | None) -> str:
    if not user_id:
        return "-"
    return f"{user_id[:8]}..."


@router.get("/me")
async def get_admin_me(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "is_admin": is_admin_user(current_user),
        "user_id": current_user.id,
        "email": current_user.email,
    }


@router.get("/overview")
async def get_admin_overview(
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_admin(current_user)

    now = datetime.now(timezone.utc)
    start_30 = (now - timedelta(days=30)).isoformat()
    start_14 = (now - timedelta(days=13)).date()
    today = now.date().isoformat()

    sessions = _safe_table_rows(
        supabase,
        "counseling_sessions",
        "id,user_id,status,started_at,ended_at,created_at,persona",
        limit=5000,
        order_by="started_at",
    )
    recent_sessions = sessions[:12]
    session_ids = [row["id"] for row in sessions if row.get("id")]

    profiles = _safe_table_rows(
        supabase,
        "user_profiles",
        "user_id,display_name,gender,birth_year,created_at,updated_at,onboarding_profile",
        limit=5000,
        order_by="created_at",
    )
    profile_by_user = {row.get("user_id"): row for row in profiles}

    survey_rows = _safe_table_rows(
        supabase,
        "survey_responses",
        "session_id,phase,question_key,emoji_value,score,created_at",
        limit=5000,
        order_by="created_at",
        gte=("created_at", start_30),
    )
    watched_rows = _safe_table_rows(
        supabase,
        "watched_content_records",
        "user_id,session_id,content_id,content_title,thumbnail_url,media_provider,watched_at",
        limit=5000,
        order_by="watched_at",
        gte=("watched_at", start_30),
    )
    feedback_rows = _safe_table_rows(
        supabase,
        "content_feedback",
        "user_id,session_id,content_id,feedback,created_at",
        limit=5000,
        order_by="created_at",
        gte=("created_at", start_30),
    )
    emotion_rows = _safe_table_rows(
        supabase,
        "emotion_records",
        "user_id,session_id,emotion,intensity,created_at",
        limit=5000,
        order_by="created_at",
        gte=("created_at", start_30),
    )
    recommendation_rows = _safe_table_rows(
        supabase,
        "recommendation_log",
        "user_id,session_id,search_query,video_id,video_title,emotion,intensity,feedback,created_at",
        limit=5000,
        order_by="created_at",
        gte=("created_at", start_30),
    )
    message_rows = _safe_table_rows(
        supabase,
        "counseling_history",
        "session_id,role,created_at",
        limit=5000,
        order_by="created_at",
        gte=("created_at", start_30),
    )

    active_users_30 = {
        row.get("user_id")
        for row in sessions
        if row.get("user_id") and (_parse_ts(row.get("started_at")) or now) >= now - timedelta(days=30)
    }
    total_feedback = len(feedback_rows)
    likes = sum(1 for row in feedback_rows if row.get("feedback") == "like")
    dislikes = sum(1 for row in feedback_rows if row.get("feedback") == "dislike")
    completed_sessions = sum(1 for row in sessions if row.get("status") == "completed" or row.get("ended_at"))
    active_sessions = sum(1 for row in sessions if row.get("status") == "active" and not row.get("ended_at"))

    daily = {
        (start_14 + timedelta(days=idx)).isoformat(): {
            "date": (start_14 + timedelta(days=idx)).isoformat(),
            "sessions": 0,
            "messages": 0,
            "watched": 0,
            "feedback": 0,
            "average_mood": None,
        }
        for idx in range(14)
    }
    mood_scores: dict[str, list[float]] = defaultdict(list)
    for row in sessions:
        key = _date_key(row.get("started_at"))
        if key in daily:
            daily[key]["sessions"] += 1
    for row in message_rows:
        key = _date_key(row.get("created_at"))
        if key in daily:
            daily[key]["messages"] += 1
    for row in watched_rows:
        key = _date_key(row.get("watched_at"))
        if key in daily:
            daily[key]["watched"] += 1
    for row in feedback_rows:
        key = _date_key(row.get("created_at"))
        if key in daily:
            daily[key]["feedback"] += 1
    for row in survey_rows:
        if row.get("question_key") != "mood_general":
            continue
        key = _date_key(row.get("created_at"))
        if key in daily:
            try:
                mood_scores[key].append(float(row.get("score")))
            except (TypeError, ValueError):
                pass
    for key, scores in mood_scores.items():
        if scores:
            daily[key]["average_mood"] = round(sum(scores) / len(scores), 2)

    mood_labels = {
        "great": "아주 좋아요",
        "good": "괜찮아요",
        "neutral": "그저 그래요",
        "low": "조금 힘들어요",
        "bad": "많이 힘들어요",
    }
    mood_distribution = Counter(
        row.get("emoji_value")
        for row in survey_rows
        if row.get("question_key") == "mood_general" and row.get("emoji_value")
    )
    emotion_distribution = Counter(row.get("emotion") for row in emotion_rows if row.get("emotion"))
    persona_distribution = Counter(row.get("persona") or "미선택" for row in sessions)
    media_distribution = Counter(row.get("media_provider") or "unknown" for row in watched_rows)

    content_stats: dict[str, dict[str, Any]] = {}
    for row in watched_rows:
        content_id = row.get("content_id")
        if not content_id:
            continue
        item = content_stats.setdefault(
            content_id,
            {
                "content_id": content_id,
                "title": row.get("content_title") or "제목 없음",
                "media_provider": row.get("media_provider") or "unknown",
                "thumbnail_url": row.get("thumbnail_url"),
                "watched_count": 0,
                "likes": 0,
                "dislikes": 0,
            },
        )
        item["watched_count"] += 1
    for row in feedback_rows:
        content_id = row.get("content_id")
        if not content_id:
            continue
        item = content_stats.setdefault(
            content_id,
            {
                "content_id": content_id,
                "title": "시청 기록 없음",
                "media_provider": "unknown",
                "thumbnail_url": None,
                "watched_count": 0,
                "likes": 0,
                "dislikes": 0,
            },
        )
        if row.get("feedback") == "like":
            item["likes"] += 1
        elif row.get("feedback") == "dislike":
            item["dislikes"] += 1

    message_count_by_session = Counter(row.get("session_id") for row in message_rows if row.get("session_id"))
    watched_count_by_session = Counter(row.get("session_id") for row in watched_rows if row.get("session_id"))
    latest_mood_by_session: dict[str, dict[str, Any]] = {}
    for row in survey_rows:
        sid = row.get("session_id")
        if not sid or row.get("question_key") != "mood_general":
            continue
        prev = latest_mood_by_session.get(sid)
        if not prev or str(row.get("created_at")) > str(prev.get("created_at")):
            latest_mood_by_session[sid] = row

    return {
        "generated_at": now.isoformat(),
        "window_days": 30,
        "metrics": {
            "total_users": max(len(profiles), len({row.get("user_id") for row in sessions if row.get("user_id")})),
            "active_users_30d": len(active_users_30),
            "total_sessions": _safe_count(supabase, "counseling_sessions"),
            "active_sessions": active_sessions,
            "completed_sessions": completed_sessions,
            "today_sessions": sum(1 for row in sessions if _date_key(row.get("started_at")) == today),
            "messages_30d": len(message_rows),
            "survey_responses_30d": len(survey_rows),
            "watched_content_30d": len(watched_rows),
            "feedback_30d": total_feedback,
            "likes_30d": likes,
            "dislikes_30d": dislikes,
            "emotion_records_30d": len(emotion_rows),
            "recommendations_30d": len(recommendation_rows),
        },
        "daily_activity": list(daily.values()),
        "mood_distribution": [
            {"key": key, "label": mood_labels.get(str(key), str(key)), "count": count}
            for key, count in mood_distribution.most_common()
        ],
        "emotion_distribution": [
            {"emotion": key, "count": count}
            for key, count in emotion_distribution.most_common(8)
        ],
        "persona_distribution": [
            {"persona": key, "count": count}
            for key, count in persona_distribution.most_common()
        ],
        "media_distribution": [
            {"media_provider": key, "count": count}
            for key, count in media_distribution.most_common()
        ],
        "top_content": sorted(
            content_stats.values(),
            key=lambda item: (item["watched_count"], item["likes"]),
            reverse=True,
        )[:10],
        "recent_sessions": [
            {
                "session_id": row.get("id"),
                "user_id": row.get("user_id"),
                "user_label": profile_by_user.get(row.get("user_id"), {}).get("display_name")
                or _short_user_id(row.get("user_id")),
                "status": row.get("status"),
                "persona": row.get("persona") or "미선택",
                "started_at": row.get("started_at"),
                "ended_at": row.get("ended_at"),
                "message_count": message_count_by_session.get(row.get("id"), 0),
                "watched_count": watched_count_by_session.get(row.get("id"), 0),
                "latest_mood": mood_labels.get(
                    str(latest_mood_by_session.get(row.get("id"), {}).get("emoji_value")),
                    latest_mood_by_session.get(row.get("id"), {}).get("emoji_value"),
                ),
            }
            for row in recent_sessions
        ],
    }
