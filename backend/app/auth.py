from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt
from supabase import Client

from app.config import get_settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: Optional[str] = None
    role: Optional[str] = None


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

    secret = get_settings().supabase_jwt_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable",
        )

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    return CurrentUser(
        id=str(user_id),
        email=payload.get("email"),
        role=payload.get("role"),
    )


def require_same_user(requested_user_id: str, current_user: CurrentUser) -> None:
    if requested_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own data",
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
