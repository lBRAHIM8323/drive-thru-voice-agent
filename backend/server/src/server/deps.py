"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from .db import get_session
from .models import User
from .security import decode_token

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


def require_role(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role {' or '.join(roles)} required, got {user.role!r}",
            )
        return user
    return checker


def require_branch_resource(
    user: User = Depends(get_current_user),
) -> uuid.UUID | None:
    if user.role == "admin":
        return None
    if user.branch_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"{user.role} must be assigned to a branch",
        )
    return user.branch_id
