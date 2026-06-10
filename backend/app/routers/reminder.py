from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from supabase import Client

from app.auth import CurrentUser, get_current_user, require_same_user
from app.services.supabase_service import get_supabase_client


router = APIRouter(prefix="/reminder", tags=["reminder"])


class ReminderPreferenceRequest(BaseModel):
    user_id: str
    enabled: bool = True
    reminder_time: str = "22:00"
    timezone: str = "Asia/Seoul"

    @field_validator("reminder_time")
    @classmethod
    def validate_reminder_time(cls, value: str) -> str:
        try:
            parts = value.split(":")
            if len(parts) != 2:
                raise ValueError("invalid time format")
            hour = int(parts[0])
            minute = int(parts[1])
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("invalid time range")
            return f"{hour:02d}:{minute:02d}"
        except Exception as exc:
            raise ValueError("reminder_time must be HH:MM format") from exc


class ReminderMarkSentRequest(BaseModel):
    user_id: str


def _select_due_users(raw_rows: list[dict], now_utc: datetime) -> list[dict]:
    due_users = []

    for row in raw_rows:
        tz_name = row.get("timezone") or "Asia/Seoul"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        local_now = now_utc.astimezone(tz)
        reminder_time = (row.get("reminder_time") or "22:00:00")[:5]
        hour, minute = reminder_time.split(":")

        if local_now.hour != int(hour) or local_now.minute != int(minute):
            continue

        last_sent_at = row.get("last_sent_at")
        if last_sent_at:
            try:
                last_sent_local = datetime.fromisoformat(last_sent_at.replace("Z", "+00:00")).astimezone(tz)
                if last_sent_local.date() == local_now.date():
                    continue
            except Exception:
                pass

        due_users.append(
            {
                "user_id": row["user_id"],
                "timezone": tz_name,
                "reminder_time": reminder_time,
            }
        )

    return due_users


def _insert_dispatch_log(
    supabase: Client,
    *,
    user_id: str,
    status_text: str,
    source: str,
    detail: str | None = None,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("reminder_dispatch_logs").insert(
        {
            "user_id": user_id,
            "status": status_text,
            "source": source,
            "detail": detail,
            "created_at": now_iso,
        }
    ).execute()


def dispatch_due_reminders(supabase: Client, source: str = "scheduler") -> dict:
    now_utc = datetime.now(timezone.utc)
    result = supabase.table("user_reminder_preferences").select("*").eq(
        "enabled", True
    ).execute()

    due_users = _select_due_users(result.data or [], now_utc)
    sent_count = 0
    failed_count = 0

    for item in due_users:
        user_id = item["user_id"]
        try:
            # 실제 발송 채널 연결 전까지는 dispatch log + mark-sent로 중복 발송만 방지
            _insert_dispatch_log(
                supabase,
                user_id=user_id,
                status_text="sent",
                source=source,
                detail=f"placeholder dispatch at {item['reminder_time']} ({item['timezone']})",
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            supabase.table("user_reminder_preferences").update(
                {
                    "last_sent_at": now_iso,
                    "updated_at": now_iso,
                }
            ).eq("user_id", user_id).execute()
            sent_count += 1
        except Exception as e:
            failed_count += 1
            try:
                _insert_dispatch_log(
                supabase,
                user_id=user_id,
                status_text="failed",
                source=source,
                detail=type(e).__name__,
            )
            except Exception:
                pass

    return {
        "status": "ok",
        "checked_at": now_utc.isoformat(),
        "due_count": len(due_users),
        "sent_count": sent_count,
        "failed_count": failed_count,
        "due_users": due_users,
    }


@router.put("/preferences")
async def upsert_reminder_preference(
    payload: ReminderPreferenceRequest,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        require_same_user(payload.user_id, current_user)
        now_iso = datetime.now(timezone.utc).isoformat()

        result = supabase.table("user_reminder_preferences").upsert(
            {
                "user_id": payload.user_id,
                "enabled": payload.enabled,
                "reminder_time": f"{payload.reminder_time}:00",
                "timezone": payload.timezone,
                "updated_at": now_iso,
            },
            on_conflict="user_id",
        ).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                "user_id": row["user_id"],
                "enabled": row["enabled"],
                "reminder_time": row["reminder_time"][:5],
                "timezone": row.get("timezone", "Asia/Seoul"),
                "updated_at": row.get("updated_at"),
            }

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save reminder preference",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/preferences/{user_id}")
async def get_reminder_preference(
    user_id: str,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        require_same_user(user_id, current_user)
        result = supabase.table("user_reminder_preferences").select("*").eq(
            "user_id", user_id
        ).limit(1).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                "user_id": row["user_id"],
                "enabled": row["enabled"],
                "reminder_time": row["reminder_time"][:5],
                "timezone": row.get("timezone", "Asia/Seoul"),
                "last_sent_at": row.get("last_sent_at"),
            }

        return {
            "user_id": user_id,
            "enabled": True,
            "reminder_time": "22:00",
            "timezone": "Asia/Seoul",
            "last_sent_at": None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/due")
async def get_due_reminders(
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        now_utc = datetime.now(timezone.utc)
        result = supabase.table("user_reminder_preferences").select("*").eq(
            "enabled", True
        ).execute()

        due_users = _select_due_users(result.data or [], now_utc)

        return {
            "status": "ok",
            "checked_at": now_utc.isoformat(),
            "due_count": len(due_users),
            "due_users": due_users,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/mark-sent")
async def mark_reminder_sent(
    payload: ReminderMarkSentRequest,
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        require_same_user(payload.user_id, current_user)
        now_iso = datetime.now(timezone.utc).isoformat()
        result = supabase.table("user_reminder_preferences").update(
            {
                "last_sent_at": now_iso,
                "updated_at": now_iso,
            }
        ).eq("user_id", payload.user_id).execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reminder preference not found",
            )

        return {
            "status": "ok",
            "user_id": payload.user_id,
            "last_sent_at": now_iso,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/dispatch")
async def dispatch_due_reminder_now(
    supabase: Client = Depends(get_supabase_client),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        return dispatch_due_reminders(supabase, source="manual-api")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
