import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Annotated, Literal

from dotenv import load_dotenv
from pydantic import Field

from .config import AgentConfig
from .config_loader import load_agent_config
from .database import (
    COMMON_INSTRUCTIONS,
    FakeDB,
    MenuItem,
    find_items_by_id,
    menu_instructions,
)
from .menu_client import fetch_menu, format_menu_items
from .models import build_llm, build_stt, build_tts, build_turn_detection, build_vad
from .order import OrderedCombo, OrderedHappy, OrderedRegular, OrderState

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AudioConfig,
    BackgroundAudioPlayer,
    FunctionTool,
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
    drink_items: list[MenuItem]
    combo_items: list[MenuItem]
    happy_items: list[MenuItem]
    regular_items: list[MenuItem]
    sauce_items: list[MenuItem]


class DriveThruAgent(Agent):
    def __init__(
        self, *, userdata: Userdata, instructions_prefix: str = COMMON_INSTRUCTIONS
    ) -> None:
        instructions = (
            instructions_prefix
            + "\n\n"
            + menu_instructions("drink", items=userdata.drink_items)
            + "\n\n"
            + menu_instructions("combo_meal", items=userdata.combo_items)
            + "\n\n"
            + menu_instructions("happy_meal", items=userdata.happy_items)
            + "\n\n"
            + menu_instructions("regular", items=userdata.regular_items)
            + "\n\n"
            + menu_instructions("sauce", items=userdata.sauce_items)
        )

        super().__init__(
            instructions=instructions,
            tools=[
                self.build_regular_order_tool(
                    userdata.regular_items, userdata.drink_items, userdata.sauce_items
                ),
                self.build_combo_order_tool(
                    userdata.combo_items, userdata.drink_items, userdata.sauce_items
                ),
                self.build_happy_order_tool(
                    userdata.happy_items, userdata.drink_items, userdata.sauce_items
                ),
            ],
        )

    def build_combo_order_tool(
        self, combo_items: list[MenuItem], drink_items: list[MenuItem], sauce_items: list[MenuItem]
    ) -> FunctionTool:
        available_combo_ids = {item.id for item in combo_items}
        available_drink_ids = {item.id for item in drink_items}
        available_sauce_ids = {item.id for item in sauce_items}

        @function_tool
        async def order_combo_meal(
            ctx: RunContext[Userdata],
            meal_id: Annotated[
                str,
                Field(
                    description="The ID of the combo meal the user requested.",
                    json_schema_extra={"enum": list(available_combo_ids)},
                ),
            ],
            drink_id: Annotated[
                str,
                Field(
                    description="The ID of the drink the user requested.",
                    json_schema_extra={"enum": list(available_drink_ids)},
                ),
            ],
            drink_size: Literal["M", "L", "null"] | None,
            fries_size: Literal["M", "L"],
            sauce_id: Annotated[
                str,
                Field(
                    description="The ID of the sauce the user requested.",
                    json_schema_extra={"enum": [*available_sauce_ids, "null"]},
                ),
            ]
            | None,
        ):
            """
            Call this when the user orders a **Combo Meal**, like: “Number 4b with a large Sprite” or “I'll do a medium meal.”

            Do not call this tool unless the user clearly refers to a known combo meal by name or number.
            Regular items like a single cheeseburger cannot be made into a meal unless such a combo explicitly exists.

            Only call this function once the user has clearly specified both a drink and a sauce — always ask for them if they're missing.
            Never infer or assume the drink — if the user has not explicitly named a drink, ask for it before calling this tool.

            A meal can only be Medium or Large; Small is not an available option.
            Drink and fries sizes can differ (e.g., “large fries but a medium Coke”).

            If the user says just “a large meal,” assume both drink and fries are that size.
            """
            if not find_items_by_id(combo_items, meal_id):
                raise ToolError(f"error: the meal {meal_id} was not found")

            drink_sizes = find_items_by_id(drink_items, drink_id)
            if not drink_sizes:
                raise ToolError(f"error: the drink {drink_id} was not found")

            if drink_size == "null":
                drink_size = None

            if sauce_id == "null":
                sauce_id = None

            available_sizes = list({item.size for item in drink_sizes if item.size})
            if drink_size is None and len(available_sizes) > 1:
                raise ToolError(
                    f"error: {drink_id} comes with multiple sizes: {', '.join(available_sizes)}. "
                    "Please clarify which size should be selected."
                )

            if drink_size is not None and not available_sizes:
                raise ToolError(
                    f"error: size should not be specified for item {drink_id} as it does not support sizing options."
                )

            available_sizes = list({item.size for item in drink_sizes if item.size})
            if drink_size not in available_sizes:
                drink_size = None
                # raise ToolError(
                #     f"error: unknown size {drink_size} for {drink_id}. Available sizes: {', '.join(available_sizes)}."
                # )

            if sauce_id and not find_items_by_id(sauce_items, sauce_id):
                raise ToolError(f"error: the sauce {sauce_id} was not found")

            item = OrderedCombo(
                meal_id=meal_id,
                drink_id=drink_id,
                drink_size=drink_size,
                sauce_id=sauce_id,
                fries_size=fries_size,
            )
            await ctx.userdata.order.add(item)
            return f"The item was added: {item.model_dump_json()}"

        return order_combo_meal

    def build_happy_order_tool(
        self,
        happy_items: list[MenuItem],
        drink_items: list[MenuItem],
        sauce_items: list[MenuItem],
    ) -> FunctionTool:
        available_happy_ids = {item.id for item in happy_items}
        available_drink_ids = {item.id for item in drink_items}
        available_sauce_ids = {item.id for item in sauce_items}

        @function_tool
        async def order_happy_meal(
            ctx: RunContext[Userdata],
            meal_id: Annotated[
                str,
                Field(
                    description="The ID of the happy meal the user requested.",
                    json_schema_extra={"enum": list(available_happy_ids)},
                ),
            ],
            drink_id: Annotated[
                str,
                Field(
                    description="The ID of the drink the user requested.",
                    json_schema_extra={"enum": list(available_drink_ids)},
                ),
            ],
            drink_size: Literal["S", "M", "L", "null"] | None,
            sauce_id: Annotated[
                str,
                Field(
                    description="The ID of the sauce the user requested.",
                    json_schema_extra={"enum": [*available_sauce_ids, "null"]},
                ),
            ]
            | None,
        ) -> str:
            """
            Call this when the user orders a **Happy Meal**, typically for children. These meals come with a main item, a drink, and a sauce.

            The user must clearly specify a valid Happy Meal option (e.g., “Can I get a Happy Meal?”).

            Before calling this tool:
            - Ensure the user has provided all required components: a valid meal, drink, drink size, and sauce.
            - If any of these are missing, prompt the user for the missing part before proceeding.

            Assume Small as default only if the user says "Happy Meal" and gives no size preference, but always ask for clarification if unsure.
            """
            if not find_items_by_id(happy_items, meal_id):
                raise ToolError(f"error: the meal {meal_id} was not found")

            drink_sizes = find_items_by_id(drink_items, drink_id)
            if not drink_sizes:
                raise ToolError(f"error: the drink {drink_id} was not found")

            if drink_size == "null":
                drink_size = None

            if sauce_id == "null":
                sauce_id = None

            available_sizes = list({item.size for item in drink_sizes if item.size})
            if drink_size is None and len(available_sizes) > 1:
                raise ToolError(
                    f"error: {drink_id} comes with multiple sizes: {', '.join(available_sizes)}. "
                    "Please clarify which size should be selected."
                )

            if drink_size is not None and not available_sizes:
                drink_size = None

            if sauce_id and not find_items_by_id(sauce_items, sauce_id):
                raise ToolError(f"error: the sauce {sauce_id} was not found")

            item = OrderedHappy(
                meal_id=meal_id,
                drink_id=drink_id,
                drink_size=drink_size,
                sauce_id=sauce_id,
            )
            await ctx.userdata.order.add(item)
            return f"The item was added: {item.model_dump_json()}"

        return order_happy_meal

    def build_regular_order_tool(
        self,
        regular_items: list[MenuItem],
        drink_items: list[MenuItem],
        sauce_items: list[MenuItem],
    ) -> FunctionTool:
        all_items = regular_items + drink_items + sauce_items
        available_ids = {item.id for item in all_items}

        @function_tool
        async def order_regular_item(
            ctx: RunContext[Userdata],
            item_id: Annotated[
                str,
                Field(
                    description="The ID of the item the user requested.",
                    json_schema_extra={"enum": list(available_ids)},
                ),
            ],
            size: Annotated[
                # models don't seem to understand `ItemSize | None`, adding the `null` inside the enum list as a workaround
                Literal["S", "M", "L", "null"] | None,
                Field(
                    description="Size of the item, if applicable (e.g., 'S', 'M', 'L'), otherwise 'null'. "
                ),
            ] = "null",
        ) -> str:
            """
            Call this when the user orders **a single item on its own**, not as part of a Combo Meal or Happy Meal.

            The customer must provide clear and specific input. For example, item variants such as flavor must **always** be explicitly stated.
            Never call this tool when size information is still needed — if the item has multiple sizes and the user has not specified one, ask for the size before calling.

            The user might say—for example:
            - “Just the cheeseburger, no meal”
            - “A medium Coke”
            - “Can I get some ketchup?”
            - “Can I get a McFlurry Oreo?”
            """
            item_sizes = find_items_by_id(all_items, item_id)
            if not item_sizes:
                raise ToolError(f"error: {item_id} was not found.")

            if size == "null":
                size = None

            available_sizes = list({item.size for item in item_sizes if item.size})
            if size is None and len(available_sizes) > 1:
                raise ToolError(
                    f"error: {item_id} comes with multiple sizes: {', '.join(available_sizes)}. "
                    "Please clarify which size should be selected."
                )

            if size is not None and not available_sizes:
                size = None
                # raise ToolError(
                #     f"error: size should not be specified for item {item_id} as it does not support sizing options."
                # )

            if (size and available_sizes) and size not in available_sizes:
                raise ToolError(
                    f"error: unknown size {size} for {item_id}. Available sizes: {', '.join(available_sizes)}."
                )

            item = OrderedRegular(item_id=item_id, size=size)
            await ctx.userdata.order.add(item)
            return f"The item was added: {item.model_dump_json()}"

        return order_regular_item

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


def _find(items: list[MenuItem], id: str, size=None) -> MenuItem | None:
    found = find_items_by_id(items, id, size)
    return found[0] if found else None


def build_cart(userdata: Userdata) -> dict:
    """Build a structured cart payload for the customer frontend.

    Identical lines (same name + details) are aggregated into a single entry
    with a quantity. Shape:
        {"currency", "items": [{name, details, quantity, unit_price,
                                line_total, image_url}], "total"}
    `image_url` is null until the agent is wired to the server-managed menu.
    """
    # Preserve insertion order while aggregating duplicates by (name, details).
    aggregated: dict[tuple[str, str], dict] = {}
    for item in userdata.order.items.values():
        if isinstance(item, OrderedCombo):
            meal = _find(userdata.combo_items, item.meal_id)
            drink = _find(userdata.drink_items, item.drink_id, item.drink_size)
            extras = [f"fries {item.fries_size}"]
            if drink:
                extras.append(f"{drink.name} ({item.drink_size})")
            if item.sauce_id:
                sauce = _find(userdata.sauce_items, item.sauce_id)
                if sauce:
                    extras.append(sauce.name)
            name = meal.name if meal else item.meal_id
            price = meal.price if meal else 0.0
        elif isinstance(item, OrderedHappy):
            meal = _find(userdata.happy_items, item.meal_id)
            drink = _find(userdata.drink_items, item.drink_id, item.drink_size)
            extras = []
            if drink:
                extras.append(f"{drink.name} ({item.drink_size})")
            if item.sauce_id:
                sauce = _find(userdata.sauce_items, item.sauce_id)
                if sauce:
                    extras.append(sauce.name)
            name = meal.name if meal else item.meal_id
            price = meal.price if meal else 0.0
        else:
            assert isinstance(item, OrderedRegular)
            reg = _find(userdata.regular_items, item.item_id, item.size)
            name = reg.name if reg else item.item_id
            price = reg.price if reg else 0.0
            extras = [f"size {item.size}"] if item.size else []

        details = ", ".join(extras)
        key = (name, details)
        if key in aggregated:
            entry = aggregated[key]
            entry["quantity"] += 1
            entry["line_total"] = round(entry["unit_price"] * entry["quantity"], 2)
        else:
            aggregated[key] = {
                "name": name,
                "details": details or None,
                "quantity": 1,
                "unit_price": round(price, 2),
                "line_total": round(price, 2),
                "image_url": None,
            }

    items = list(aggregated.values())
    total = round(sum(e["line_total"] for e in items), 2)
    return {"currency": "USD", "items": items, "total": total}


async def new_userdata() -> Userdata:
    fake_db = FakeDB()
    drink_items = await fake_db.list_drinks()
    combo_items = await fake_db.list_combo_meals()
    happy_items = await fake_db.list_happy_meals()
    regular_items = await fake_db.list_regulars()
    sauce_items = await fake_db.list_sauces()

    order_state = OrderState(items={})
    userdata = Userdata(
        order=order_state,
        drink_items=drink_items,
        combo_items=combo_items,
        happy_items=happy_items,
        regular_items=regular_items,
        sauce_items=sauce_items,
    )
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

    async def _push_to(identity: str, payload: str) -> None:
        try:
            await ctx.room.local_participant.perform_rpc(
                destination_identity=identity,
                method="set_cart_content",
                payload=payload,
            )
        except Exception:
            logger.exception("cart push to %s failed", identity)

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
                    *(_push_to(p.identity, payload) for p in peers),
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
