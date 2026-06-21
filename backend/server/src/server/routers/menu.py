"""Menu item CRUD (with normalized per-size pricing + R2 image upload)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import boto3
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

from ..db import get_session
from ..deps import get_current_user, require_branch_resource
from ..models import MenuItem, MenuItemSize, User
from ..schemas.menu import (
    ItemCategory,
    MenuItemCreate,
    MenuItemRead,
    MenuItemUpdate,
    SizeOption,
)
from ..settings import get_settings

router = APIRouter(prefix="/menu", tags=["menu"])


def _r2_client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=s.r2_access_key,
        aws_secret_access_key=s.r2_secret_key,
        region_name="auto",
    )


def slugify(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.strip().lower()).strip("_")


def _offer_is_live(item: MenuItem) -> bool:
    if item.offer_price is None:
        return False
    if item.offer_until is None:
        return True
    until = item.offer_until
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until >= datetime.now(timezone.utc)


def _to_read(item: MenuItem) -> MenuItemRead:
    return MenuItemRead(
        id=item.id,
        name=item.name,
        category=item.category,  # type: ignore[arg-type]
        description=item.description,
        available=item.available,
        voice_alias=item.voice_alias,
        image_url=item.image_url,
        calories=item.calories,
        price=item.price,
        currency=item.currency,
        branch_id=item.branch_id,
        dietary=item.dietary,  # type: ignore[arg-type]
        tags=item.tags or [],
        serves=item.serves,
        is_favorite=item.is_favorite,
        offer_price=item.offer_price,
        offer_until=item.offer_until,
        sizes=[SizeOption(size=s.size, price=s.price, calories=s.calories) for s in item.sizes],  # type: ignore[arg-type]
    )


def _apply_sizes(item: MenuItem, sizes: list[SizeOption]) -> None:
    item.sizes = [
        MenuItemSize(size=s.size, price=s.price, calories=s.calories) for s in sizes
    ]


@router.get("", response_model=list[MenuItemRead])
def list_menu(
    category: ItemCategory | None = Query(default=None),
    favorite: bool | None = Query(
        default=None, description="Filter to admin-marked customer favourites."
    ),
    on_offer: bool | None = Query(
        default=None, description="Filter to items with a currently-live limited-time offer."
    ),
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
) -> list[MenuItemRead]:
    stmt = select(MenuItem)
    if category:
        stmt = stmt.where(MenuItem.category == category)
    if favorite is not None:
        stmt = stmt.where(MenuItem.is_favorite == favorite)
    if user_branch_id is not None:
        stmt = stmt.where(
            (MenuItem.branch_id == user_branch_id) | (MenuItem.branch_id.is_(None))
        )
    items = session.exec(stmt).all()
    if on_offer is not None:
        items = [i for i in items if _offer_is_live(i) == on_offer]
    return [_to_read(i) for i in items]


@router.post("", response_model=MenuItemRead, status_code=201)
def create_menu_item(
    payload: MenuItemCreate,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    user: User = Depends(get_current_user),
) -> MenuItemRead:
    item_id = payload.id or slugify(payload.name)
    if session.get(MenuItem, item_id):
        raise HTTPException(409, f"menu item {item_id!r} already exists")

    if user.role not in ("admin", "manager"):
        raise HTTPException(403, "Only admin and manager can create menu items")
    branch_id = payload.branch_id
    if user_branch_id is not None:
        if branch_id is not None and branch_id != user_branch_id:
            raise HTTPException(403, "Cannot create items for another branch")
        branch_id = user_branch_id

    item = MenuItem(
        id=item_id,
        branch_id=branch_id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        available=payload.available,
        voice_alias=payload.voice_alias,
        image_url=payload.image_url,
        calories=payload.calories,
        price=payload.price,
        currency=payload.currency,
        dietary=payload.dietary,
        tags=payload.tags,
        serves=payload.serves,
        is_favorite=payload.is_favorite,
        offer_price=payload.offer_price,
        offer_until=payload.offer_until,
    )
    _apply_sizes(item, payload.sizes)
    session.add(item)
    session.commit()
    session.refresh(item)
    return _to_read(item)


@router.get("/{item_id}", response_model=MenuItemRead)
def get_menu_item(
    item_id: str,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    _user: User = Depends(get_current_user),
) -> MenuItemRead:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404, f"menu item {item_id!r} not found")
    if user_branch_id is not None and item.branch_id is not None and item.branch_id != user_branch_id:
        raise HTTPException(403, "Access denied to this menu item")
    return _to_read(item)


@router.patch("/{item_id}", response_model=MenuItemRead)
def update_menu_item(
    item_id: str,
    payload: MenuItemUpdate,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    user: User = Depends(get_current_user),
) -> MenuItemRead:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404, f"menu item {item_id!r} not found")

    if user.role != "admin":
        if user_branch_id is None or item.branch_id != user_branch_id:
            raise HTTPException(403, "Access denied to this menu item")

    data = payload.model_dump(exclude_unset=True)
    if user_branch_id is not None:
        data.pop("branch_id", None)
    sizes = data.pop("sizes", None)
    for field, value in data.items():
        setattr(item, field, value)
    if sizes is not None:
        _apply_sizes(item, [SizeOption.model_validate(s) for s in sizes])
    session.add(item)
    session.commit()
    session.refresh(item)
    return _to_read(item)


@router.delete("/{item_id}", status_code=204)
def delete_menu_item(
    item_id: str,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    user: User = Depends(get_current_user),
) -> None:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404, f"menu item {item_id!r} not found")
    if user.role != "admin":
        if user_branch_id is None or item.branch_id != user_branch_id:
            raise HTTPException(403, "Access denied to this menu item")
    session.delete(item)
    session.commit()


@router.post("/{item_id}/image", response_model=MenuItemRead)
def upload_item_image(
    item_id: str,
    file: UploadFile,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    user: User = Depends(get_current_user),
) -> MenuItemRead:
    """Upload an image file for a menu item, store it in Cloudflare R2, and set ``image_url``."""
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404, f"menu item {item_id!r} not found")
    if user.role != "admin":
        if user_branch_id is None or item.branch_id != user_branch_id:
            raise HTTPException(403, "Access denied to this menu item")

    s = get_settings()
    if not all([s.r2_account_id, s.r2_access_key, s.r2_secret_key, s.r2_bucket_name]):
        raise HTTPException(500, "Cloudflare R2 is not configured")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "jpg"
    key = f"menu/{item_id}/{uuid.uuid4().hex}.{ext}"

    body = file.file.read()
    if len(body) > 5 * 1024 * 1024:
        raise HTTPException(413, "Image exceeds 5 MB limit")

    client = _r2_client()
    client.put_object(
        Bucket=s.r2_bucket_name,
        Key=key,
        Body=body,
        ContentType=file.content_type or "image/jpeg",
    )

    public_url = f"{s.r2_public_base_url.rstrip('/')}/{key}"
    item.image_url = public_url
    session.add(item)
    session.commit()
    session.refresh(item)
    return _to_read(item)
