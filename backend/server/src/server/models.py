"""SQLModel database tables — the mature drive-thru schema.

Money is stored as ``Numeric(12, 2)`` (returned as ``float`` via
``asdecimal=False``) so JSON stays numeric. Enum-like columns are plain strings
validated at the Pydantic/schema layer (kept simple for create-all migrations).
Timestamps are DB-side (``server_default``/``onupdate`` using ``func.now()``).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.types import JSON
from sqlmodel import Field, Relationship, SQLModel


# --- shared column helpers ------------------------------------------------


def _created_at() -> Any:
    return Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


def _updated_at() -> Any:
    return Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )


def _money(*, nullable: bool = True) -> Any:
    return Field(
        default=None,
        sa_column=Column(Numeric(12, 2, asdecimal=False), nullable=nullable),
    )


def _uuid_pk() -> Any:
    return Field(default_factory=uuid.uuid4, primary_key=True)


# --- auth -----------------------------------------------------------------


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = _uuid_pk()
    username: str = Field(unique=True, index=True)
    email: str | None = Field(default=None, unique=True, index=True)
    hashed_password: str
    role: str = "admin"
    branch_id: uuid.UUID | None = Field(
        default=None, foreign_key="branches.id", index=True
    )
    is_active: bool = True
    last_login_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime | None = _created_at()
    updated_at: datetime | None = _updated_at()


# --- franchise ------------------------------------------------------------


class Branch(SQLModel, table=True):
    __tablename__ = "branches"

    id: uuid.UUID = _uuid_pk()
    name: str
    slug: str = Field(unique=True, index=True)
    address: str | None = None
    city: str | None = None
    country: str | None = None
    currency: str = "USD"  # ISO 4217
    timezone: str = "UTC"
    phone: str | None = None
    is_active: bool = True
    created_at: datetime | None = _created_at()
    updated_at: datetime | None = _updated_at()


# --- menu -----------------------------------------------------------------


class MenuItem(SQLModel, table=True):
    __tablename__ = "menu_items"

    id: str = Field(primary_key=True)  # slug, e.g. "coca_cola" (used by the agent)
    branch_id: uuid.UUID | None = Field(
        default=None, foreign_key="branches.id", index=True
    )  # null == applies to all branches
    name: str
    category: str  # drink | combo_meal | happy_meal | regular | sauce
    description: str | None = None
    available: bool = True
    voice_alias: str | None = None
    image_url: str | None = None
    calories: int | None = None
    # Base price for non-size-selectable items; size rows hold per-size pricing.
    price: float | None = _money()
    currency: str = "USD"
    created_at: datetime | None = _created_at()
    updated_at: datetime | None = _updated_at()

    sizes: list["MenuItemSize"] = Relationship(
        back_populates="item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class MenuItemSize(SQLModel, table=True):
    __tablename__ = "menu_item_sizes"
    __table_args__ = (UniqueConstraint("menu_item_id", "size", name="uq_menu_item_size"),)

    id: uuid.UUID = _uuid_pk()
    menu_item_id: str = Field(
        sa_column=Column(ForeignKey("menu_items.id", ondelete="CASCADE"), index=True)
    )
    size: str  # S | M | L | XL
    price: float = _money(nullable=False)
    calories: int | None = None

    item: MenuItem | None = Relationship(back_populates="sizes")


# --- documents (menu uploads + parsing) -----------------------------------


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: uuid.UUID = _uuid_pk()
    branch_id: uuid.UUID | None = Field(default=None, foreign_key="branches.id", index=True)
    uploaded_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    storage_path: str | None = None
    status: str = "parsed"  # uploaded | parsing | parsed | failed | confirmed
    parser_provider: str | None = None
    parser_model: str | None = None
    # Parsed output: {"items": [DraftMenuItem, ...]}.
    parsed_response: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error: str | None = None
    created_at: datetime | None = _created_at()
    updated_at: datetime | None = _updated_at()
    parsed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


# --- configuration --------------------------------------------------------


class AgentConfigRecord(SQLModel, table=True):
    __tablename__ = "agent_configs"

    id: str = Field(primary_key=True)
    branch_id: uuid.UUID | None = Field(default=None, foreign_key="branches.id", index=True)
    name: str = ""
    is_active: bool = False
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime | None = _created_at()
    updated_at: datetime | None = _updated_at()


class ParserConfigRecord(SQLModel, table=True):
    __tablename__ = "parser_config"

    id: int | None = Field(default=1, primary_key=True)  # singleton row
    provider: str = "anthropic"
    model: str = "claude-haiku-4-5"
    temperature: float | None = None
    system_prompt: str | None = None


# --- sessions & orders ----------------------------------------------------


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: uuid.UUID = _uuid_pk()
    branch_id: uuid.UUID | None = Field(default=None, foreign_key="branches.id", index=True)
    agent_config_id: str | None = Field(default=None, foreign_key="agent_configs.id")
    room_name: str | None = None
    status: str = "active"  # active | completed | abandoned
    started_at: datetime | None = _created_at()
    ended_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    audio_url: str | None = None  # later scope
    transcript: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    orders: list["Order"] = Relationship(back_populates="session")


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: uuid.UUID = _uuid_pk()
    session_id: uuid.UUID | None = Field(default=None, foreign_key="sessions.id", index=True)
    branch_id: uuid.UUID | None = Field(default=None, foreign_key="branches.id", index=True)
    status: str = "pending"  # pending | confirmed | preparing | completed | cancelled
    subtotal: float = _money(nullable=False)
    tax: float = _money(nullable=False)
    total: float = _money(nullable=False)
    currency: str = "USD"
    placed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime | None = _created_at()
    updated_at: datetime | None = _updated_at()

    session: Session | None = Relationship(back_populates="orders")
    items: list["OrderItem"] = Relationship(
        back_populates="order",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    id: uuid.UUID = _uuid_pk()
    order_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    )
    # Nullable so deleting a menu item doesn't erase order history.
    menu_item_id: str | None = Field(
        default=None, sa_column=Column(ForeignKey("menu_items.id", ondelete="SET NULL"))
    )
    name_snapshot: str  # name at time of order
    size: str | None = None
    quantity: int = 1
    unit_price: float = _money(nullable=False)
    total_price: float = _money(nullable=False)
    notes: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    order: Order | None = Relationship(back_populates="items")
