"""Schemas for franchise branches."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class BranchBase(BaseModel):
    name: str
    address: str | None = None
    city: str | None = None
    country: str | None = None
    currency: str = "USD"
    timezone: str = "UTC"
    phone: str | None = None
    is_active: bool = True


class BranchCreate(BranchBase):
    slug: str | None = None  # generated from name if omitted


class BranchUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    currency: str | None = None
    timezone: str | None = None
    phone: str | None = None
    is_active: bool | None = None


class BranchRead(BranchBase):
    id: uuid.UUID
    slug: str
    created_at: datetime | None
    updated_at: datetime | None
