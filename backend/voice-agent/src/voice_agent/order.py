from __future__ import annotations

import logging
import secrets
import string
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

logger = logging.getLogger("drive-thru.order")


def order_uid() -> str:
    alphabet = string.ascii_uppercase + string.digits  # b36
    return "O_" + "".join(secrets.choice(alphabet) for _ in range(6))


class OrderedItem(BaseModel):
    """A single line in the order, snapshotting the menu item at order time.

    Name/price/size are stored on the item itself so the cart never needs to
    re-query the menu (and historical prices are preserved even if the menu
    changes).
    """

    order_id: str = Field(default_factory=order_uid)
    item_id: str
    name: str
    size: str | None = None
    quantity: int = 1
    unit_price: float = 0.0
    currency: str = "USD"
    image_url: str | None = None


@dataclass
class OrderState:
    items: dict[str, OrderedItem]
    # Optional async hook fired after every add/remove. The agent wires this up
    # to push the current cart to the frontend; exceptions inside the hook never
    # block the order mutation.
    on_change: Callable[[], Awaitable[None]] | None = field(default=None)

    async def _fire(self) -> None:
        if self.on_change is None:
            return
        try:
            await self.on_change()
        except Exception:
            logger.exception("OrderState.on_change failed")

    async def add(self, item: OrderedItem) -> None:
        self.items[item.order_id] = item
        await self._fire()

    async def remove(self, order_id: str) -> OrderedItem:
        removed = self.items.pop(order_id)
        await self._fire()
        return removed

    def get(self, order_id: str) -> OrderedItem | None:
        return self.items.get(order_id)
