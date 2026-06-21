"""Pydantic request/response schemas for menu items and parser config."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Category is free-form: it's whatever section the menu uses (e.g. "coffee",
# "tea", "burgers", "drinks"). Not constrained to any one franchise's taxonomy.
ItemCategory = str
ItemSize = Literal["S", "M", "L", "XL"]
# Veg/non-veg classification. Free-form-ish but constrained to the common set so
# the agent and UI can render a consistent badge.
Dietary = Literal["veg", "non_veg", "vegan"]
ParserProvider = Literal["openai", "anthropic", "google"]


class SizeOption(BaseModel):
    size: ItemSize
    price: float
    calories: int | None = None


class MenuItemBase(BaseModel):
    name: str
    category: ItemCategory
    description: str | None = None
    available: bool = True
    voice_alias: str | None = None
    image_url: str | None = None
    calories: int | None = None
    price: float | None = None
    currency: str = "USD"
    branch_id: uuid.UUID | None = None
    # Dietary classification + free-form tags (e.g. "lactose_free", "gluten_free").
    dietary: Dietary | None = None
    tags: list[str] = Field(default_factory=list)
    # Number of people a meal feeds (null for single-serve items).
    serves: int | None = None
    # Admin-marked customer favourite (used for greeting upsell).
    is_favorite: bool = False
    # Limited-time offer: discounted price valid until ``offer_until``.
    offer_price: float | None = None
    offer_until: datetime | None = None
    sizes: list[SizeOption] = Field(default_factory=list)


class MenuItemCreate(MenuItemBase):
    # Slug id, e.g. "coca_cola". Generated from the name if omitted.
    id: str | None = None


class MenuItemUpdate(BaseModel):
    name: str | None = None
    category: ItemCategory | None = None
    description: str | None = None
    available: bool | None = None
    voice_alias: str | None = None
    image_url: str | None = None
    calories: int | None = None
    price: float | None = None
    currency: str | None = None
    branch_id: uuid.UUID | None = None
    dietary: Dietary | None = None
    tags: list[str] | None = None
    serves: int | None = None
    is_favorite: bool | None = None
    offer_price: float | None = None
    offer_until: datetime | None = None
    sizes: list[SizeOption] | None = None


class MenuItemRead(MenuItemBase):
    id: str


# A single parsed item (same shape as a create payload). A parsed document
# holds a list of these for the admin to review/edit before committing.
class DraftMenuItem(MenuItemCreate):
    pass


class ParserConfigRead(BaseModel):
    provider: ParserProvider
    model: str
    temperature: float | None = None
    system_prompt: str | None = None


class ParserConfigUpdate(BaseModel):
    provider: ParserProvider | None = None
    model: str | None = None
    temperature: float | None = None
    system_prompt: str | None = None
