import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx
from dotenv import load_dotenv
from pydantic import Field

from .config import AgentConfig
from .config_loader import load_agent_config
from .database import COMMON_INSTRUCTIONS
from .menu_client import (
    CUTLERY_ITEMS,
    effective_unit_price,
    fetch_menu,
    format_menu_items,
    offer_is_live,
)
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
    StopResponse,
    ToolError,
    cli,
    function_tool,
)
from livekit.agents.llm import ChatContext, ChatMessage

load_dotenv()

logger = logging.getLogger("drive-thru")


# Remote participants whose identity starts with this prefix are treated as
# human staff who can take over a call (they sit muted in the room until needed).
STAFF_IDENTITY_PREFIX = "staff"


@dataclass
class Userdata:
    order: OrderState
    # Set by the session runtime; the `transfer_to_human` tool calls this to hand
    # the live conversation over to a human staffer who is already in the room.
    # Returns True if a staff member was present to take over.
    request_handoff: Callable[[str], Awaitable[bool]] | None = field(default=None)


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
        # Handoff/observer state. When a human staffer takes over the call, the
        # agent goes silent (audio output muted by the runtime) and switches to
        # "observing": it stops replying and instead records the human↔customer
        # exchange as notes, so the resolution can be reviewed/learned from.
        self._observing = False
        self._handoff_reason: str | None = None
        self._handoff_notes: list[dict[str, Any]] = []

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """While a human is handling the call, don't reply — just take notes.

        Both the customer and the (now-unmuted) staffer are transcribed as user
        turns; we log each one and raise ``StopResponse`` so the LLM stays quiet.
        """
        if not self._observing:
            return
        text = (new_message.text_content or "").strip()
        if text:
            self._handoff_notes.append(
                {"text": text, "at": datetime.now(timezone.utc).isoformat()}
            )
        raise StopResponse()

    def begin_observing(self, reason: str) -> None:
        self._observing = True
        self._handoff_reason = reason

    def drain_handoff(self) -> dict[str, Any] | None:
        """Return the recorded handoff episode (and reset), or None if none."""
        if self._handoff_reason is None and not self._handoff_notes:
            return None
        episode = {"reason": self._handoff_reason, "notes": list(self._handoff_notes)}
        self._handoff_reason = None
        self._handoff_notes = []
        self._observing = False
        return episode

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
            items = await _all_menu_items()
        except Exception as e:
            raise ToolError(f"error: could not load the menu: {e}")

        item = next((i for i in items if i["id"] == item_id), None)
        if item is None:
            raise ToolError(
                f"error: '{item_id}' is not on the menu. Use search_menu_items to find the correct id."
            )
        if not item.get("available", True):
            alts = _similar_available_items(items, item)
            if alts:
                names = ", ".join(a["name"] for a in alts)
                raise ToolError(
                    f"error: {item['name']} is out of order for the day. "
                    f"Offer the customer a similar available item instead: {names}."
                )
            raise ToolError(
                f"error: {item['name']} is out of order for the day and there's no "
                "close substitute. Let the customer know and suggest browsing the menu."
            )

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
            # Honour a live limited-time offer price when the item has no sizes.
            unit_price = effective_unit_price(item) or 0.0

        qty = max(1, int(quantity))
        if qty > 20:
            raise ToolError(
                f"Sorry, I can't process {qty} x {item['name']}. "
                "Please limit your order to 20 or fewer of any single item."
            )
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
            items = await _all_menu_items(category)
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
            items = await _all_menu_items()
        except Exception as e:
            raise ToolError(f"error: could not load the menu: {e}")

        q = query.lower()
        matches = [i for i in items if q in i["name"].lower()]
        if not matches:
            return f"No menu items match '{query}'."
        return "Matching items:\n" + format_menu_items(matches, include_id=True)

    @function_tool
    async def get_featured_items(self, ctx: RunContext[Userdata]) -> str:
        """
        List the items worth recommending right now: customer favourites and any
        live limited-time offers.

        Use this to make a friendly upsell suggestion — e.g. on the opening
        greeting ("Would you like to try our…?") or when the customer is unsure
        what to order. Only suggest items this tool returns; never invent a deal.
        """
        try:
            items = await _all_menu_items()
        except Exception as e:
            raise ToolError(f"error: could not load the menu: {e}")

        featured = [
            i
            for i in items
            if i.get("available", True) and (i.get("is_favorite") or offer_is_live(i))
        ]
        if not featured:
            return "No featured items or active offers right now."
        return "Featured / on offer:\n" + format_menu_items(featured, include_id=True)

    @function_tool
    async def transfer_to_human(
        self,
        ctx: RunContext[Userdata],
        reason: Annotated[
            str,
            Field(
                description="A short summary of why a human is needed (e.g. "
                "'customer wants a refund', 'I misunderstood the order twice', "
                "'complaint about a previous visit')."
            ),
        ],
    ) -> str:
        """
        Hand the live conversation over to a human team member who is already on
        the line (muted) — for example a manager or supervisor.

        Use when the customer explicitly asks for a person, or when you've made a
        mistake / don't understand and can't recover (repeated misunderstandings,
        complaints, refunds). After this, the human speaks with the customer
        directly and YOU go quiet — you'll keep listening and taking notes, but
        you must not speak again unless the human hands the call back.
        """
        request_handoff = ctx.userdata.request_handoff
        if request_handoff is None:
            raise ToolError(
                "error: handoff isn't available right now. Apologise and do your best "
                "to help, or offer to take a callback number."
            )

        # Confirm a staffer is present (and signal them to take over) BEFORE we
        # promise the customer anything.
        try:
            staff_present = await request_handoff(reason)
        except Exception as e:
            raise ToolError(f"error: the handoff failed: {e}. Apologise and keep helping.")

        if not staff_present:
            raise ToolError(
                "error: no team member is available right now. Let the customer know "
                "a staffer will be with them shortly, or offer to keep helping yourself."
            )

        # Announce the hand-off and let the line finish playing before we go silent.
        try:
            await ctx.session.say(
                "Of course — let me bring a team member in to help you. One moment."
            ).wait_for_playout()
        except Exception:
            logger.exception("failed to announce handoff")

        # Mute our own voice and switch to silent note-taking. The human takes over.
        self.begin_observing(reason)
        try:
            ctx.session.output.set_audio_enabled(False)
        except Exception:
            logger.exception("failed to mute agent audio for handoff")
        return (
            "A team member is now taking over. Do not speak further — stay silent "
            "and observe. (This handoff is being recorded as notes.)"
        )


def _similar_available_items(
    items: list[dict[str, Any]], target: dict[str, Any], limit: int = 3
) -> list[dict[str, Any]]:
    """Pick up to ``limit`` available items in the same category as ``target`` —
    used to suggest a substitute when the requested item is out of order."""
    category = (target.get("category") or "").lower()
    return [
        i
        for i in items
        if i["id"] != target["id"]
        and i.get("available", True)
        and (i.get("category") or "").lower() == category
    ][:limit]


async def _all_menu_items(category: str | None = None) -> list[dict[str, Any]]:
    """Fetch menu from the server and merge built-in cutlery/add-on items."""
    items = await fetch_menu(category)
    if category is None:
        items.extend(CUTLERY_ITEMS)
    elif category.lower() in ("add-ons", "add ons", "addons"):
        items = list(CUTLERY_ITEMS)
    return items


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

# Per-room agent registry so `on_session_end` (which only gets the JobContext)
# can reach the agent and flush any human-handoff notes it recorded.
_ACTIVE_AGENTS: dict[str, "DriveThruAgent"] = {}


async def _post_handoff_notes(room_name: str, episode: dict[str, Any]) -> None:
    server_url = os.getenv("SERVER_URL", "").rstrip("/")
    api_key = os.getenv("AGENT_API_KEY")
    if not (server_url and api_key):
        logger.info("handoff notes not persisted (SERVER_URL/AGENT_API_KEY unset): %s", episode)
        return
    try:
        url = f"{server_url}/agent/sessions/by-room/{room_name}/handoff-notes"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=episode,
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "persist handoff notes for %s returned %s: %s",
                    room_name, resp.status_code, resp.text,
                )
    except Exception:
        logger.exception("failed to persist handoff notes for %s", room_name)


async def on_session_end(ctx: JobContext) -> None:
    report = ctx.make_session_report()
    _ = json.dumps(report.to_dict(), indent=2)

    room_name = ctx.room.name

    # Flush any recorded human-handoff notes before marking the session done.
    agent = _ACTIVE_AGENTS.pop(room_name, None)
    if agent is not None:
        episode = agent.drain_handoff()
        if episode is not None:
            await _post_handoff_notes(room_name, episode)

    server_url = os.getenv("SERVER_URL", "").rstrip("/")
    api_key = os.getenv("AGENT_API_KEY")
    if not api_key:
        logger.warning("AGENT_API_KEY not set; cannot mark session %s as completed", room_name)
    if server_url and api_key:
        try:
            url = f"{server_url}/agent/sessions/by-room/{room_name}/complete"
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

    agent = DriveThruAgent(userdata=userdata, instructions_prefix=config.instructions)

    async def request_handoff(reason: str) -> bool:
        """Hand the live call to a human staffer already in the room (muted).

        Signals the staffer to unmute and take over, and tells the customer UI a
        team member is joining. Returns True only if a staffer is actually
        present. The agent itself goes quiet and starts taking notes (handled by
        the `transfer_to_human` tool).
        """
        logger.info("handoff to human requested: %s", reason)
        peers = list(ctx.room.remote_participants.values())
        staff = [p for p in peers if (p.identity or "").startswith(STAFF_IDENTITY_PREFIX)]
        if not staff:
            logger.warning("handoff requested but no staff participant in room")
            return False

        await asyncio.gather(
            *(
                _push_to(
                    p.identity,
                    "set_handoff_state",
                    json.dumps({"state": "active", "reason": reason}),
                )
                for p in staff
            ),
            return_exceptions=True,
        )
        # Tell everyone else (the customer) a human is taking over.
        customers = [p for p in peers if p not in staff]
        await asyncio.gather(
            *(
                _push_to(
                    p.identity,
                    "set_transfer_state",
                    json.dumps({"state": "connecting", "reason": reason}),
                )
                for p in customers
            ),
            return_exceptions=True,
        )
        return True

    userdata.request_handoff = request_handoff
    _ACTIVE_AGENTS[ctx.room.name] = agent

    await session.start(agent=agent, room=ctx.room)

    # Push the full menu (DB items + built-in cutlery) to the UI once at session start
    try:
        menu_items = await _all_menu_items()
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
