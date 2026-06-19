"""Dispatch an extracted document to the admin-configured LLM provider."""

from __future__ import annotations

from ..models import ParserConfigRecord
from ..schemas.menu import DraftMenuItem
from .extract import ExtractedInput
from .providers import PROVIDERS, ParserError, require_provider_key

DEFAULT_SYSTEM_PROMPT = """\
You are a menu extraction assistant. Read the provided menu (text or image) and
return ONLY a JSON object of the form:

{"items": [
  {
    "id": "snake_case_slug",            // optional; derived from name if omitted
    "name": "Display Name",
    "category": "coffee",                // the menu's own section/group, lowercase
    "available": true,
    "voice_alias": null,                 // a short code/number if the menu shows one, else null
    "calories": 590|null,                 // for items with a single price
    "price": 5.89|null,
    "sizes": [                            // ONLY for size-selectable items; else []
      {"size": "S|M|L|XL", "calories": 230, "price": 1.89}
    ]
  }
]}

Rules:
- `category` is free-form: use the menu's own section/group name in lowercase
  (e.g. "coffee", "tea", "food", "burgers", "drinks", "sides"). Do NOT force items
  into a fixed taxonomy.
- For size-selectable items put pricing in `sizes` (map size labels to S/M/L/XL)
  and leave top-level calories/price null. For single-price items use top-level
  calories/price and an empty `sizes` array.
- Infer reasonable slugs; keep names verbatim. Do not invent items not present.
- Output JSON only, no commentary.
"""


def parse_menu(extracted: ExtractedInput, parser_config: ParserConfigRecord) -> list[DraftMenuItem]:
    """Return draft items for an extracted document.

    CSV (kind == "items") is already structured and bypasses the LLM.
    """
    if extracted.kind == "items":
        return extracted.items

    fn = PROVIDERS.get(parser_config.provider)
    if fn is None:
        raise ParserError(f"unknown parser provider: {parser_config.provider!r}")

    require_provider_key(parser_config.provider)
    system = parser_config.system_prompt or DEFAULT_SYSTEM_PROMPT
    return fn(
        model=parser_config.model,
        system=system,
        temperature=parser_config.temperature,
        text=extracted.text,
        image_bytes=extracted.image_bytes,
        image_mime=extracted.image_mime,
    )
