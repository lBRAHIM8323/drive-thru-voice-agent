"""Turn an uploaded document into a normalized parser input.

Text/Markdown and PDF become text; images stay as bytes for a vision request;
CSV is parsed deterministically into draft items (no LLM needed).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Literal

from ..schemas.menu import DraftMenuItem, SizeOption


class UnsupportedFormat(Exception):
    """Raised when the upload's content type/extension isn't supported."""


@dataclass
class ExtractedInput:
    kind: Literal["text", "image", "items"]
    text: str | None = None
    image_bytes: bytes | None = None
    image_mime: str | None = None
    items: list[DraftMenuItem] = field(default_factory=list)


_TEXT_EXTS = (".txt", ".md", ".markdown")


def _slugify(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.strip().lower()).strip("_")


def _parse_csv(text: str) -> list[DraftMenuItem]:
    """Columns: id,name,category[,size,calories,price,available,voice_alias].

    Rows sharing an id are grouped; rows with a `size` populate `sizes`, rows
    without one set the item's top-level calories/price.
    """
    reader = csv.DictReader(io.StringIO(text))
    by_id: dict[str, DraftMenuItem] = {}
    order: list[str] = []

    for row in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        name = row.get("name") or ""
        if not name:
            continue
        item_id = row.get("id") or _slugify(name)
        calories = int(row["calories"]) if row.get("calories") else None
        price = float(row["price"]) if row.get("price") else None
        size = (row.get("size") or "").upper() or None

        if item_id not in by_id:
            by_id[item_id] = DraftMenuItem(
                id=item_id,
                name=name,
                category=row.get("category") or "regular",  # type: ignore[arg-type]
                available=(row.get("available", "true").lower() not in ("false", "0", "no")),
                voice_alias=row.get("voice_alias") or None,
            )
            order.append(item_id)

        item = by_id[item_id]
        if size in ("S", "M", "L"):
            item.sizes.append(
                SizeOption(size=size, calories=calories or 0, price=price or 0.0)  # type: ignore[arg-type]
            )
        else:
            item.calories = calories
            item.price = price

    return [by_id[i] for i in order]


def extract(
    *,
    raw: bytes | None = None,
    filename: str | None = None,
    content_type: str | None = None,
    text: str | None = None,
) -> ExtractedInput:
    # Direct text body (JSON {text}) always wins.
    if text is not None:
        return ExtractedInput(kind="text", text=text)

    if raw is None:
        raise UnsupportedFormat("no file or text provided")

    ct = (content_type or "").lower()
    name = (filename or "").lower()

    if ct == "text/csv" or name.endswith(".csv"):
        return ExtractedInput(kind="items", items=_parse_csv(raw.decode("utf-8", "replace")))

    if ct.startswith("image/"):
        return ExtractedInput(kind="image", image_bytes=raw, image_mime=ct or "image/png")

    if ct == "application/pdf" or name.endswith(".pdf"):
        return ExtractedInput(kind="text", text=_extract_pdf_text(raw))

    if ct in ("text/plain", "text/markdown") or name.endswith(_TEXT_EXTS) or not ct:
        return ExtractedInput(kind="text", text=raw.decode("utf-8", "replace"))

    raise UnsupportedFormat(f"unsupported upload type: {content_type or filename!r}")


def _extract_pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages).strip()
    if not text:
        raise UnsupportedFormat(
            "could not extract text from PDF (it may be scanned — upload an image instead)"
        )
    return text
