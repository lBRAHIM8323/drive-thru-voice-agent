"""Read the live, admin-managed menu from the server (backend/server)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

MENU_PATH = "/agent/menu"
_TIMEOUT = 10.0

# Built-in add-on / cutlery items always available to order. These are merged
# into the DB-sourced menu by the agent so customers can request them by voice.
CUTLERY_ITEMS: list[dict[str, Any]] = [
    {
        "id": "extra_spoon",
        "name": "Extra Spoon",
        "category": "Add-ons",
        "description": None,
        "available": True,
        "voice_alias": None,
        "image_url": None,
        "calories": None,
        "price": 0.0,
        "currency": "USD",
        "branch_id": None,
        "sizes": [],
    },
    {
        "id": "extra_fork",
        "name": "Extra Fork",
        "category": "Add-ons",
        "description": None,
        "available": True,
        "voice_alias": None,
        "image_url": None,
        "calories": None,
        "price": 0.0,
        "currency": "USD",
        "branch_id": None,
        "sizes": [],
    },
    {
        "id": "extra_knife",
        "name": "Extra Knife",
        "category": "Add-ons",
        "description": None,
        "available": True,
        "voice_alias": None,
        "image_url": None,
        "calories": None,
        "price": 0.0,
        "currency": "USD",
        "branch_id": None,
        "sizes": [],
    },
    {
        "id": "extra_napkins",
        "name": "Extra Napkins",
        "category": "Add-ons",
        "description": None,
        "available": True,
        "voice_alias": None,
        "image_url": None,
        "calories": None,
        "price": 0.0,
        "currency": "USD",
        "branch_id": None,
        "sizes": [],
    },
]


async def fetch_menu(category: str | None = None) -> list[dict[str, Any]]:
    """GET the current menu items, optionally filtered by category."""
    base = os.getenv("SERVER_URL")
    if not base:
        raise RuntimeError("SERVER_URL is not set; cannot reach the menu service")

    url = base.rstrip("/") + MENU_PATH
    params = {"category": category} if category else None
    headers = {}
    api_key = os.getenv("AGENT_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def offer_is_live(item: dict[str, Any]) -> bool:
    """True when the item has a discounted ``offer_price`` whose ``offer_until``
    deadline is open-ended or still in the future."""
    if item.get("offer_price") is None:
        return False
    until = _parse_dt(item.get("offer_until"))
    if until is None:
        return True
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until >= datetime.now(timezone.utc)


def effective_unit_price(item: dict[str, Any]) -> float | None:
    """The price the customer pays for a non-size item: the live offer price if
    one is running, otherwise the regular base price."""
    if offer_is_live(item):
        return item.get("offer_price")
    return item.get("price")


def _price_label(item: dict[str, Any]) -> str:
    currency = item.get("currency") or "USD"
    sizes = item.get("sizes") or []
    if sizes:
        return ", ".join(f"{s['size']} {currency} {s['price']:.2f}" for s in sizes)
    if offer_is_live(item):
        regular = item.get("price")
        offer = item.get("offer_price")
        if regular is not None and regular != offer:
            return f"{currency} {offer:.2f} (offer, was {regular:.2f})"
        return f"{currency} {offer:.2f} (offer)"
    price = item.get("price")
    return f"{currency} {price:.2f}" if price is not None else "price n/a"


def format_menu_items(items: list[dict[str, Any]], *, include_id: bool = False) -> str:
    """Render menu items as a compact, voice-friendly list for the LLM.

    Pass ``include_id=True`` when the LLM needs the exact ``item_id`` to order.
    """
    lines: list[str] = []
    for item in items:
        ident = f" [id: {item['id']}]" if include_id else ""
        line = f"- {item['name']}{ident} ({item.get('category', 'item')}): {_price_label(item)}"
        if item.get("calories") is not None:
            line += f", {item['calories']} Cal"
        dietary = item.get("dietary")
        if dietary:
            line += f", {dietary.replace('_', '-')}"
        tags = item.get("tags") or []
        if tags:
            line += f", {', '.join(str(t).replace('_', ' ') for t in tags)}"
        if item.get("serves"):
            line += f", serves {item['serves']}"
        if item.get("is_favorite"):
            line += " ⭐ customer favourite"
        if offer_is_live(item):
            until = _parse_dt(item.get("offer_until"))
            line += " 🔥 limited-time offer"
            if until is not None:
                line += f" (until {until.date().isoformat()})"
        if item.get("description"):
            line += f" — {item['description']}"
        if not item.get("available", True):
            line += " [UNAVAILABLE]"
        lines.append(line)
    return "\n".join(lines)
