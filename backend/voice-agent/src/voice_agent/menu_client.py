"""Read the live, admin-managed menu from the server (backend/server)."""

from __future__ import annotations

import os
from typing import Any

import httpx

MENU_PATH = "/api/v1/menu"
_TIMEOUT = 10.0


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


def _price_label(item: dict[str, Any]) -> str:
    currency = item.get("currency") or "USD"
    sizes = item.get("sizes") or []
    if sizes:
        return ", ".join(f"{s['size']} {currency} {s['price']:.2f}" for s in sizes)
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
        if item.get("description"):
            line += f" — {item['description']}"
        if not item.get("available", True):
            line += " [UNAVAILABLE]"
        lines.append(line)
    return "\n".join(lines)
