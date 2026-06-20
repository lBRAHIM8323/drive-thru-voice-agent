from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None = None
    role: str
    branch_id: uuid.UUID | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    email: str | None = None
    role: str = "staff"
    branch_id: uuid.UUID | None = None
    is_active: bool = True


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    email: str | None = None
    role: str | None = None
    branch_id: uuid.UUID | None = None
    is_active: bool | None = None
