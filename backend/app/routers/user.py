from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from app.auth import CurrentUser, get_current_user, require_same_user
from app.services.supabase_service import get_supabase_client
from app.time_utils import local_day_to_utc_range, parse_iso_date
from app.routers.survey import _mood_general_pre_post


router = APIRouter(prefix="/user", tags=["user"])


def _mood_label_ko(emoji_key: Optional[str]) -> str:
    if not emoji_key:
        return "기록 없음"
    labels = {
        "great": "아주 좋음",
        "good": "좋음",
        "neutral": "보통",
        "low": "조금 어려움",
        "bad": "많이 힘듦",
    }
    return labels.get(emoji_key, emoji_key)


def _parse_supabase_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    avatar_url: Optional[str] = None
    created_at: str


class UserProfileUpsertRequest(BaseModel):
    user_id: str
    display_name: str
    gender: Optional[str] = None
    birth_year: Optional[int] = None


@router.get("/profile/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    """사용자 프로필 조회"""
    try:
        require_same_user(user_id, current_user)
        profile_result = supabase.table("user_profiles").select(
            "display_name, gender, birth_year, created_at"
        ).eq("user_id", user_id).limit(1).execute()

        if profile_result.data and len(profile_result.data) > 0:
            profile = profile_result.data[0]
            return {
                "id": user_id,
                "email": f"user_{user_id[:8]}@moodpick.local",  # 임시
                "name": profile.get("display_name") or f"User {user_id[:4]}",
                "gender": profile.get("gender"),
                "birth_year": profile.get("birth_year"),
                "avatar_url": None,
                "created_at": profile["created_at"],
            }

        session_result = supabase.table("counseling_sessions").select(
            "created_at"
        ).eq("user_id", user_id).order("created_at", desc=False).limit(1).execute()

        created_at = (
            session_result.data[0]["created_at"]
            if session_result.data and len(session_result.data) > 0
            else "1970-01-01T00:00:00+00:00"
        )

        return {
            "id": user_id,
            "email": f"user_{user_id[:8]}@moodpick.local",
            "name": f"User {user_id[:4]}",
            "gender": None,
            "birth_year": None,
            "avatar_url": None,
            "created_at": created_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/profile")
async def upsert_user_profile(
    payload: UserProfileUpsertRequest,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    """사용자 프로필 이름 저장/수정"""
    try:
        require_same_user(payload.user_id, current_user)
        display_name = payload.display_name.strip()
        if not display_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="display_name is required",
            )

        result = supabase.table("user_profiles").upsert(
            {
                "user_id": payload.user_id,
                "display_name": display_name,
                "gender": payload.gender,
                "birth_year": payload.birth_year,
            },
            on_conflict="user_id",
        ).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                "status": "success",
                "user_id": row["user_id"],
                "display_name": row["display_name"],
                "gender": row.get("gender"),
                "birth_year": row.get("birth_year"),
            }

        return {
            "status": "success",
            "user_id": payload.user_id,
            "display_name": display_name,
            "gender": payload.gender,
            "birth_year": payload.birth_year,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/sessions/{user_id}")
async def get_user_sessions(
    user_id: str,
    limit: int = 10,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    """사용자의 세션 목록 조회 (최근 10개)"""
    try:
        require_same_user(user_id, current_user)
        result = supabase.table("counseling_sessions").select("*").eq(
            "user_id", user_id
        ).order("started_at", desc=True).limit(limit).execute()

        if result.data:
            return {
                "user_id": user_id,
                "sessions": result.data,
            }
        return {
            "user_id": user_id,
            "sessions": []
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/stats/{user_id}")
async def get_user_stats(
    user_id: str,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    """사용자 통계 (세션, 피드백, 시청 기록)"""
    try:
        require_same_user(user_id, current_user)
        # 세션 수
        sessions = supabase.table("counseling_sessions").select(
            "id, started_at"
        ).eq("user_id", user_id).execute()
        session_rows = sessions.data or []
        total_sessions = len(session_rows)

        tz = ZoneInfo("Asia/Seoul")
        today = datetime.now(tz).date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)
        weekly_record_dates = set()
        for row in session_rows:
            started_at = _parse_supabase_timestamp(row.get("started_at"))
            if not started_at:
                continue
            local_date = started_at.astimezone(tz).date()
            if week_start <= local_date < week_end:
                weekly_record_dates.add(local_date.isoformat())
        weekly_record_days = len(weekly_record_dates)

        # 시청 기록
        watched = supabase.table("watched_content_records").select(
            "id"
        ).eq("user_id", user_id).execute()
        total_watched = len(watched.data) if watched.data else 0

        # 피드백
        feedback = supabase.table("content_feedback").select(
            "feedback"
        ).eq("user_id", user_id).execute()
        
        total_feedback = len(feedback.data) if feedback.data else 0
        likes = len([f for f in feedback.data if f["feedback"] == "like"]) if feedback.data else 0

        return {
            "user_id": user_id,
            "total_sessions": total_sessions,
            "weekly_record_days": weekly_record_days,
            "total_content_watched": total_watched,
            "total_feedback": total_feedback,
            "likes": likes,
            "dislikes": total_feedback - likes
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/daily-summary/{user_id}")
async def get_daily_summary(
    user_id: str,
    date: str = Query(..., description="YYYY-MM-DD"),
    timezone: str = Query("Asia/Seoul"),
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """특정 로컬 날짜의 세션·문진·시청 기록 요약 (캘린더 상세용)."""
    try:
        require_same_user(user_id, current_user)
        d = parse_iso_date(date)
        start_utc, end_utc = local_day_to_utc_range(timezone, d)

        sessions_res = (
            supabase.table("counseling_sessions")
            .select("id, started_at, ended_at, status")
            .eq("user_id", user_id)
            .gte("started_at", start_utc.isoformat())
            .lt("started_at", end_utc.isoformat())
            .order("started_at", desc=False)
            .execute()
        )
        sessions = sessions_res.data or []
        session_ids = [s["id"] for s in sessions]
        moods = _mood_general_pre_post(supabase, session_ids)

        pre_first: Optional[str] = None
        post_last: Optional[str] = None
        for sid in session_ids:
            pre, post = moods.get(sid, (None, None))
            if pre is not None:
                pre_first = pre
                break
        for sid in reversed(session_ids):
            pre, post = moods.get(sid, (None, None))
            if post is not None:
                post_last = post
                break

        improved: Optional[bool] = None
        delta_average: Optional[float] = None
        if session_ids:
            primary = session_ids[0]
            delta_res = (
                supabase.table("survey_responses")
                .select("*")
                .eq("session_id", primary)
                .execute()
            )
            rows = delta_res.data or []
            pre_scores: dict[str, float] = {}
            post_scores: dict[str, float] = {}
            for row in rows:
                key = row["question_key"]
                sc = float(row["score"])
                if row["phase"] == "pre":
                    pre_scores[key] = sc
                else:
                    post_scores[key] = sc
            deltas = [
                post_scores[k] - pre_scores[k]
                for k in pre_scores
                if k in post_scores
            ]
            if deltas:
                delta_average = sum(deltas) / len(deltas)
                improved = delta_average > 0

        watched_res = (
            supabase.table("watched_content_records")
            .select("id, content_id, content_title, thumbnail_url, watched_at, session_id")
            .eq("user_id", user_id)
            .gte("watched_at", start_utc.isoformat())
            .lt("watched_at", end_utc.isoformat())
            .order("watched_at", desc=True)
            .execute()
        )
        content_rows = watched_res.data or []
        seen_content_keys: set[tuple[Optional[str], str]] = set()
        contents = []
        for row in content_rows:
            key = (row.get("session_id"), row.get("content_id"))
            if key in seen_content_keys:
                continue
            seen_content_keys.add(key)
            contents.append(row)

        summary_lines = [
            "상담 대화 원문은 서버에 저장되지 않습니다. 아래는 해당 날짜의 문진·세션·콘텐츠 기록을 바탕으로 한 요약입니다.",
        ]
        if pre_first:
            summary_lines.append(f"· 사전 문진(하루 시작) 기분: {_mood_label_ko(pre_first)}")
        else:
            summary_lines.append("· 사전 문진: 해당 날짜에 기록이 없습니다.")
        if post_last:
            summary_lines.append(f"· 사후 문진(하루 마무리) 기분: {_mood_label_ko(post_last)}")
        else:
            summary_lines.append("· 사후 문진: 해당 날짜에 기록이 없거나 아직 마무리되지 않았습니다.")
        if delta_average is not None:
            tag = "전반적으로 개선으로 보여요." if improved else "큰 변화 없음이거나 어려움이 이어졌을 수 있어요."
            summary_lines.append(f"· 문진 점수 변화(첫 세션 기준): 평균 {delta_average:+.2f}. {tag}")
        summary_lines.append(f"· 해당 날짜 상담 세션 수: {len(sessions)}")
        summary_lines.append(f"· 시청·기록된 콘텐츠: {len(contents)}건")

        counseling_summary = "\n".join(summary_lines)

        return {
            "date": date,
            "timezone": timezone,
            "sessions": sessions,
            "pre_mood_general": pre_first,
            "post_mood_general": post_last,
            "improved": improved,
            "delta_average": delta_average,
            "contents": contents,
            "counseling_summary": counseling_summary,
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date must be YYYY-MM-DD",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
