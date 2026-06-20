"""User management (admin only)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..deps import get_current_user, require_role
from ..models import User
from ..schemas.auth import UserCreate, UserRead, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("admin")),
) -> list[User]:
    return session.exec(select(User).order_by(User.created_at)).all()


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("admin")),
) -> User:
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing:
        raise HTTPException(409, f"username {payload.username!r} already exists")
    if payload.email:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(409, f"email {payload.email!r} already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        branch_id=payload.branch_id,
        is_active=payload.is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("admin")),
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, f"user {user_id} not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("admin")),
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, f"user {user_id} not found")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        data["hashed_password"] = hash_password(data.pop("password"))
    for field, value in data.items():
        setattr(user, field, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("admin")),
) -> None:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, f"user {user_id} not found")
    session.delete(user)
    session.commit()
