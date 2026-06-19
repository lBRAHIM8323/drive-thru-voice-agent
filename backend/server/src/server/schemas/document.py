"""Schemas for uploaded menu documents and their parsed result."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .menu import DraftMenuItem

DocumentStatus = Literal["uploaded", "parsing", "parsed", "failed", "confirmed"]


class DocumentRead(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID | None
    filename: str | None
    content_type: str | None
    status: DocumentStatus
    parser_provider: str | None
    parser_model: str | None
    items: list[DraftMenuItem]
    error: str | None
    created_at: datetime | None
    parsed_at: datetime | None


class DocumentItemsUpdate(BaseModel):
    items: list[DraftMenuItem]
