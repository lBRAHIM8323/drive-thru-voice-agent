"""Menu item CRUD (with normalized per-size pricing)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import MenuItem, MenuItemSize
from ..schemas.menu import (
    ItemCategory,
    MenuItemCreate,
    MenuItemRead,
    MenuItemUpdate,
    SizeOption,
)

router = APIRouter(prefix="/menu", tags=["menu"])


def slugify(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.strip().lower()).strip("_")


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
        sizes=[SizeOption(size=s.size, price=s.price, calories=s.calories) for s in item.sizes],  # type: ignore[arg-type]
    )


def _apply_sizes(item: MenuItem, sizes: list[SizeOption]) -> None:
    item.sizes = [
        MenuItemSize(size=s.size, price=s.price, calories=s.calories) for s in sizes
    ]


@router.get("", response_model=list[MenuItemRead])
def list_menu(
    category: ItemCategory | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[MenuItemRead]:
    stmt = select(MenuItem)
    if category:
        stmt = stmt.where(MenuItem.category == category)
    return [_to_read(i) for i in session.exec(stmt).all()]


@router.post("", response_model=MenuItemRead, status_code=201)
def create_menu_item(
    payload: MenuItemCreate, session: Session = Depends(get_session)
) -> MenuItemRead:
    item_id = payload.id or slugify(payload.name)
    if session.get(MenuItem, item_id):
        raise HTTPException(409, f"menu item {item_id!r} already exists")

    item = MenuItem(
        id=item_id,
        branch_id=payload.branch_id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        available=payload.available,
        voice_alias=payload.voice_alias,
        image_url=payload.image_url,
        calories=payload.calories,
        price=payload.price,
        currency=payload.currency,
    )
    _apply_sizes(item, payload.sizes)
    session.add(item)
    session.commit()
    session.refresh(item)
    return _to_read(item)


@router.get("/{item_id}", response_model=MenuItemRead)
def get_menu_item(item_id: str, session: Session = Depends(get_session)) -> MenuItemRead:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404, f"menu item {item_id!r} not found")
    return _to_read(item)


@router.patch("/{item_id}", response_model=MenuItemRead)
def update_menu_item(
    item_id: str, payload: MenuItemUpdate, session: Session = Depends(get_session)
) -> MenuItemRead:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404, f"menu item {item_id!r} not found")

    data = payload.model_dump(exclude_unset=True)
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
def delete_menu_item(item_id: str, session: Session = Depends(get_session)) -> None:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404, f"menu item {item_id!r} not found")
    session.delete(item)
    session.commit()
