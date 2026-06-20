"""Schemas for sessions and orders."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class OrderItemRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    menu_item_id: str | None = None
    name_snapshot: str
    size: str | None = None
    quantity: int
    unit_price: float
    total_price: float
    notes: dict | None = None


class OrderRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    status: str
    subtotal: float
    tax: float
    total: float
    currency: str
    placed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    items: list[OrderItemRead] = []


class SessionRead(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID | None = None
    agent_config_id: str | None = None
    room_name: str | None = None
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    audio_url: str | None = None
    transcript: dict | None = None
    orders: list[OrderRead] = []
