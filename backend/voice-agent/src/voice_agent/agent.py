import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Annotated

import httpx
from dotenv import load_dotenv
from pydantic import Field

from .config import AgentConfig
from .config_loader import load_agent_config
from .database import COMMON_INSTRUCTIONS
from .menu_client import fetch_menu, format_menu_items
from .models import build_llm, build_stt, build_tts, build_turn_detection, build_vad
from .order import OrderedItem, OrderState

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AudioConfig,
    BackgroundAudioPlayer,
    JobContext,
    RunContext,
    ToolError,
    cli,
    function_tool,
)

load_dotenv()

logger = logging.getLogger("drive-thru")


@dataclass
class Userdata:
    order: OrderState


class DriveThruAgent(Agent):
    def __init__(
        self,
        *,
        instructions_prefix: str = COMMON_INSTRUCTIONS,
        userdata: Userdata | None = None,
    ) -> None:
        # The menu is read live via tools (get_menu_items / search_menu_items /
        # order_item) rather than injected into the prompt. `userdata` is accepted
        # for call-site compatibility but unused here.
        super().__init__(instructions=instructions_prefix)

    @function_tool
    async def order_item(
        self,
        ctx: RunContext[Userdata],
        item_id: Annotated[
            str,
            Field(
                description="The exact `item_id` from `search_menu_items`. "
                "Always look it up first — do not guess."
            ),
        ],
        size: Annotated[
            str | None,
            Field(
                description="Size label (e.g. 'S', 'M', 'L') — only for items that have sizes."
            ),
        ] = None,
        quantity: Annotated[int, Field(description="How many to add.", ge=1)] = 1,
    ) -> str:
        """
        Add an item to the customer's order.

        Call `search_menu_items` first to get the correct `item_id` and confirm
        availability. Only pass `size` when the item actually has size options.
        """
        try:
            items = await fetch_menu()
        except Exception as e:
            raise ToolError(f"error: could not load the menu: {e}")

        item = next((i for i in items if i["id"] == item_id), None)
        if item is None:
            raise ToolError(
                f"error: '{item_id}' is not on the menu. Use search_menu_items to find the correct id."
            )
        if not item.get("available", True):
            raise ToolError(f"error: {item['name']} is currently unavailable.")

        sizes = item.get("sizes") or []
        chosen_size: str | None = None
        if sizes:
            valid = sorted({s["size"] for s in sizes})
            if size is None:
                raise ToolError(
                    f"error: {item['name']} comes in sizes: {', '.join(valid)}. "
                    "Ask the customer which size."
                )
            if size not in valid:
                raise ToolError(
                    f"error: size {size!r} isn't available for {item['name']}. Options: {', '.join(valid)}."
                )
            chosen_size = size
            unit_price = next(s["price"] for s in sizes if s["size"] == size)
        else:
            unit_price = item.get("price") or 0.0

        qty = max(1, int(quantity))
        ordered = OrderedItem(
            item_id=item_id,
            name=item["name"],
            size=chosen_size,
            quantity=qty,
            unit_price=float(unit_price),
            currency=item.get("currency") or "USD",
            image_url=item.get("image_url"),
        )
        await ctx.userdata.order.add(ordered)
        label = item["name"] + (f" ({chosen_size})" if chosen_size else "")
        return f"Added {qty} x {label} to the order: {ordered.model_dump_json()}"


    @function_tool
    async def remove_order_item(
        self,
        ctx: RunContext[Userdata],
        order_id: Annotated[
            list[str],
            Field(
                description="A list of internal `order_id`s of the items to remove. Use `list_order_items` to look it up if needed."
            ),
        ],
    ) -> str:
        """
        Removes one or more items from the user's order using their `order_id`s.

        Useful when the user asks to cancel or delete existing items (e.g., “Remove the cheeseburger”).

        If the `order_id`s are unknown, call `list_order_items` first to retrieve them.
        """
        not_found = [oid for oid in order_id if oid not in ctx.userdata.order.items]
        if not_found:
            raise ToolError(f"error: no item(s) found with order_id(s): {', '.join(not_found)}")

        removed_items = [await ctx.userdata.order.remove(oid) for oid in order_id]
        return "Removed items:\n" + "\n".join(item.model_dump_json() for item in removed_items)

    @function_tool
    async def list_order_items(self, ctx: RunContext[Userdata]) -> str:
        """
        Retrieves the current list of items in the user's order, including each item's internal `order_id`.

        Helpful when:
        - An `order_id` is required before modifying or removing an existing item.
        - Confirming details or contents of the current order.

        Examples:
        - User requests modifying an item, but the item's `order_id` is unknown (e.g., "Change the fries from small to large").
        - User requests removing an item, but the item's `order_id` is unknown (e.g., "Remove the cheeseburger").
        - User asks about current order details (e.g., "What's in my order so far?").
        """
        items = ctx.userdata.order.items.values()
        if not items:
            return "The order is empty"

        return "\n".join(item.model_dump_json() for item in items)

    @function_tool
    async def get_menu_items(
        self,
        ctx: RunContext[Userdata],
        category: Annotated[
            str | None,
            Field(
                description="Optional category to filter by (e.g. 'coffee', 'drinks', 'burgers'). "
                "Omit to list the whole menu."
            ),
        ] = None,
    ) -> str:
        """
        Look up the items currently on the menu, with prices and availability.

        Use this to answer questions about what's available — e.g. "What drinks
        do you have?", "How much is the latte?", "Do you have anything vegetarian?"
        — or to check an item before adding it to the order.

        Pass a `category` to narrow the results; omit it to get the full menu.
        """
        try:
            items = await fetch_menu(category)
        except Exception as e:
            raise ToolError(f"error: could not load the menu: {e}")

        if not items:
            scope = f" in category '{category}'" if category else ""
            return f"No menu items found{scope}."
        return format_menu_items(items)

    @function_tool
    async def search_menu_items(
        self,
        ctx: RunContext[Userdata],
        query: Annotated[
            str,
            Field(description="A search term to match against item names (case-insensitive). "
                  "E.g. 'burger', 'coke', 'chicken'."),
        ],
    ) -> str:
        """
        Search the menu by name to find items matching the given query.

        Use this BEFORE calling `order_item` to get the exact `item_id` and
        confirm availability. If the search returns nothing, the item is not on
        the menu — tell the customer. Do NOT guess item IDs.
        """
        try:
            items = await fetch_menu()
        except Exception as e:
            raise ToolError(f"error: could not load the menu: {e}")

        q = query.lower()
        matches = [i for i in items if q in i["name"].lower()]
        if not matches:
            return f"No menu items match '{query}'."
        return "Matching items:\n" + format_menu_items(matches, include_id=True)


def build_cart(userdata: Userdata) -> dict:
    """Build a structured cart payload for the customer frontend.

    Shape: {"currency", "items": [{name, details, quantity, unit_price,
            line_total, image_url}], "total"}.
    """
    items: list[dict] = []
    currency = "USD"
    for o in userdata.order.items.values():
        currency = o.currency or currency
        line_total = round(o.unit_price * o.quantity, 2)
        items.append(
            {
                "name": o.name,
                "details": f"Size {o.size}" if o.size else None,
                "quantity": o.quantity,
                "unit_price": round(o.unit_price, 2),
                "line_total": line_total,
                "image_url": o.image_url,
            }
        )

    total = round(sum(i["line_total"] for i in items), 2)
    return {"currency": currency, "items": items, "total": total}


async def new_userdata() -> Userdata:
    userdata = Userdata(order=OrderState(items={}))
    return userdata


def _session_kwargs(config: AgentConfig) -> dict:
    """Build the optional AgentSession kwargs, omitting unset values so the
    framework's own defaults apply."""
    s = config.session
    kwargs = {
        "max_tool_steps": s.max_tool_steps,
        "allow_interruptions": s.allow_interruptions,
        "min_interruption_duration": s.min_interruption_duration,
        "min_endpointing_delay": s.min_endpointing_delay,
        "max_endpointing_delay": s.max_endpointing_delay,
        "preemptive_generation": s.preemptive_generation,
    }
    return {k: v for k, v in kwargs.items() if v is not None}


server = AgentServer()


async def on_session_end(ctx: JobContext) -> None:
    report = ctx.make_session_report()
    _ = json.dumps(report.to_dict(), indent=2)

    room_name = ctx.room.name
    server_url = os.getenv("SERVER_URL", "").rstrip("/")
    api_key = os.getenv("AGENT_API_KEY")
    if not api_key:
        logger.warning("AGENT_API_KEY not set; cannot mark session %s as completed", room_name)
    if server_url and api_key:
        try:
            url = f"{server_url}/api/v1/sessions/by-room/{room_name}/complete"
            async with httpx.AsyncClient() as client:
                resp = await client.patch(url, headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code != 200:
                    logger.warning(
                        "mark session %s completed returned %s: %s",
                        room_name, resp.status_code, resp.text,
                    )
        except Exception:
            logger.exception("failed to mark session %s as completed", room_name)


@server.rtc_session(on_session_end=on_session_end)
async def drive_thru_agent(ctx: JobContext) -> None:
    config = await load_agent_config(ctx)
    logger.info(
        "session config: stt=%s/%s llm=%s/%s tts=%s/%s",
        config.stt.provider,
        config.stt.model,
        config.llm.provider,
        config.llm.model,
        config.tts.provider,
        config.tts.model,
    )

    userdata = await new_userdata()
    session = AgentSession[Userdata](
        userdata=userdata,
        stt=build_stt(config.stt),
        llm=build_llm(config.llm),
        tts=build_tts(config.tts),
        vad=build_vad(config.vad),
        turn_detection=build_turn_detection(config.turn_detection),
        **_session_kwargs(config),
    )

    # Push the cart as markdown to the playground's cart view
    # whenever it changes. Coalesced + serialized: rapid changes
    # (e.g. batch-remove that pops items one at a time) collapse
    # into a single trailing push of the *latest* cart state, so
    # an empty-cart payload can't get reordered behind a stale
    # mid-state push. Fire-and-forget at the call site — the
    # function tool that mutated the order shouldn't block on the
    # RPC round-trip.
    push_pending = False
    push_running = False

    async def _push_to(identity: str, method: str, payload: str) -> None:
        try:
            await ctx.room.local_participant.perform_rpc(
                destination_identity=identity,
                method=method,
                payload=payload,
            )
        except Exception:
            logger.exception("%s push to %s failed", method, identity)

    async def _push_runner() -> None:
        nonlocal push_pending, push_running
        push_running = True
        try:
            while push_pending:
                push_pending = False
                payload = json.dumps(build_cart(userdata))
                logger.info("push_cart: %d chars", len(payload))
                peers = list(ctx.room.remote_participants.values())
                if not peers:
                    continue
                await asyncio.gather(
                    *(_push_to(p.identity, "set_cart_content", payload) for p in peers),
                    return_exceptions=True,
                )
        finally:
            push_running = False

    async def push_cart() -> None:
        nonlocal push_pending
        push_pending = True
        if push_running:
            return
        asyncio.create_task(_push_runner())

    userdata.order.on_change = push_cart

    await session.start(
        agent=DriveThruAgent(userdata=userdata, instructions_prefix=config.instructions),
        room=ctx.room,
    )

    # Push the full menu to the UI once at session start
    try:
        menu_items = await fetch_menu()
        menu_payload = json.dumps({"currency": "USD", "items": menu_items})
        peers = list(ctx.room.remote_participants.values())
        if peers:
            await asyncio.gather(
                *(_push_to(p.identity, "set_menu_content", menu_payload) for p in peers),
                return_exceptions=True,
            )
    except Exception:
        logger.exception("menu push failed")

    if config.background_audio.enabled:
        background_audio = BackgroundAudioPlayer(
            ambient_sound=AudioConfig(
                str(
                    os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), "assets", "bg_noise.mp3"
                    )
                ),
                volume=config.background_audio.volume,
            ),
        )
        await background_audio.start(room=ctx.room, agent_session=session)

    if config.greeting:
        await session.say(config.greeting)


def main() -> None:
    cli.run_app(server)


if __name__ == "__main__":
    main()
