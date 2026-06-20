"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from .db import get_session
from .models import User
from .security import decode_token
from .settings import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return session.get(User, uuid.UUID(user_id))


def get_current_user(
    user: User | None = Depends(get_optional_user),
) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    return user


def get_user_or_agent(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User | None:
    """Try JWT first, then agent API key. Returns User or None for agent."""
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            user_id = payload.get("sub")
            if user_id:
                user = session.get(User, uuid.UUID(user_id))
                if user is not None and user.is_active:
                    return user
        except Exception:
            pass
        if settings.agent_api_key and credentials.credentials == settings.agent_api_key:
            return None
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


def require_role(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role {' or '.join(roles)} required, got {user.role!r}",
            )
        return user
    return checker


def verify_agent_api_key(authorization: str | None = Header(None, alias="Authorization")) -> None:
    """Verify the voice-agent's shared API key sent as ``Authorization: Bearer <key>``."""
    settings = get_settings()
    if not settings.agent_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Agent API key not configured")
    if authorization is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.agent_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid agent API key")


def require_branch_resource(
    user: User | None = Depends(get_user_or_agent),
) -> uuid.UUID | None:
    if user is None:
        return None  # agent — no branch scoping
    if user.role == "admin":
        return None
    if user.branch_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"{user.role} must be assigned to a branch",
        )
    return user.branch_id
