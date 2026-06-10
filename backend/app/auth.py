from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Header, HTTPException, status
from supabase import Client

from app.config import get_settings
from app.services.supabase_service import get_supabase_client


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: Optional[str] = None
    role: Optional[str] = None
    app_metadata: Optional[dict[str, Any]] = None
    user_metadata: Optional[dict[str, Any]] = None


def _get_user_field(user: object, field: str) -> object | None:
    if isinstance(user, dict):
        return user.get(field)
    return getattr(user, field, None)


def _optional_str(value: object | None) -> str | None:
    return str(value) if value is not None else None


def _optional_dict(value: object | None) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _csv_set(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        user_response = get_supabase_client().auth.get_user(token)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc

    user = getattr(user_response, "user", None)
    user_id = _get_user_field(user, "id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    return CurrentUser(
        id=str(user_id),
        email=_optional_str(_get_user_field(user, "email")),
        role=_optional_str(_get_user_field(user, "role")),
        app_metadata=_optional_dict(_get_user_field(user, "app_metadata")),
        user_metadata=_optional_dict(_get_user_field(user, "user_metadata")),
    )


def require_same_user(requested_user_id: str, current_user: CurrentUser) -> None:
    if requested_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own data",
        )


def is_admin_user(current_user: CurrentUser) -> bool:
    settings = get_settings()
    admin_user_ids = _csv_set(settings.admin_user_ids)
    admin_emails = _csv_set(settings.admin_emails)

    if current_user.id.lower() in admin_user_ids:
        return True
    if current_user.email and current_user.email.lower() in admin_emails:
        return True

    metadata_values = [
        current_user.role,
        current_user.app_metadata.get("role") if current_user.app_metadata else None,
        current_user.app_metadata.get("app_role") if current_user.app_metadata else None,
        current_user.app_metadata.get("admin_role") if current_user.app_metadata else None,
        current_user.user_metadata.get("role") if current_user.user_metadata else None,
        current_user.user_metadata.get("app_role") if current_user.user_metadata else None,
        current_user.user_metadata.get("admin_role") if current_user.user_metadata else None,
    ]
    if any(str(value).lower() in {"admin", "owner", "moodpick_admin"} for value in metadata_values if value):
        return True

    flag_values = [
        current_user.app_metadata.get("is_admin") if current_user.app_metadata else None,
        current_user.app_metadata.get("moodpick_admin") if current_user.app_metadata else None,
        current_user.user_metadata.get("is_admin") if current_user.user_metadata else None,
        current_user.user_metadata.get("moodpick_admin") if current_user.user_metadata else None,
    ]
    return any(value is True or str(value).lower() == "true" for value in flag_values if value is not None)


def require_admin(current_user: CurrentUser) -> None:
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


def get_owned_session(
    supabase: Client,
    session_id: str,
    user_id: str,
    *,
    select: str = "id,user_id,status",
) -> dict:
    result = (
        supabase.table("counseling_sessions")
        .select(select)
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return result.data[0]
