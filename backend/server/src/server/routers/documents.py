"""Upload + AI-parse menu documents into reviewable drafts, then commit to menu."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session, delete, select

from ..db import get_session
from ..models import Document, MenuItem, MenuItemSize, ParserConfigRecord
from ..parsing.extract import UnsupportedFormat, extract
from ..parsing.parser import parse_menu
from ..parsing.providers import MissingProviderKey, ParserError
from ..schemas.document import DocumentItemsUpdate, DocumentRead
from ..schemas.menu import DraftMenuItem
from .menu import slugify

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_read(doc: Document) -> DocumentRead:
    items = doc.parsed_response.get("items", []) if doc.parsed_response else []
    return DocumentRead(
        id=doc.id,
        branch_id=doc.branch_id,
        filename=doc.filename,
        content_type=doc.content_type,
        status=doc.status,  # type: ignore[arg-type]
        parser_provider=doc.parser_provider,
        parser_model=doc.parser_model,
        items=[DraftMenuItem.model_validate(i) for i in items],
        error=doc.error,
        created_at=doc.created_at,
        parsed_at=doc.parsed_at,
    )


def _get_parser_config(session: Session) -> ParserConfigRecord:
    cfg = session.get(ParserConfigRecord, 1)
    if cfg is None:
        cfg = ParserConfigRecord()
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    return cfg


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_and_parse(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> DocumentRead:
    """Parse an uploaded menu (file) or pasted `text` into a pending document."""
    # A real file upload takes precedence over the `text` field; `text` is only
    # used when no file is provided (avoids the Swagger default "string" winning).
    text = text if (text or "").strip() else None
    if file is None and text is None:
        raise HTTPException(400, "provide a file or text")

    raw = await file.read() if file is not None else None
    try:
        extracted = extract(
            raw=raw,
            filename=file.filename if file else None,
            content_type=file.content_type if file else None,
            text=None if file is not None else text,
        )
    except UnsupportedFormat as e:
        raise HTTPException(415, str(e)) from e

    parser_config = _get_parser_config(session)
    if extracted.kind == "items":
        provider, model = "csv", None
    else:
        provider, model = parser_config.provider, parser_config.model

    doc = Document(
        filename=file.filename if file else None,
        content_type=(file.content_type if file else "text/plain"),
        size_bytes=len(raw) if raw is not None else (len(text or "")),
        parser_provider=provider,
        parser_model=model,
    )

    try:
        items = parse_menu(extracted, parser_config)
        doc.status = "parsed"
        doc.parsed_response = {"items": [i.model_dump(mode="json") for i in items]}
        doc.parsed_at = datetime.now(timezone.utc)
    except ParserError as e:
        doc.status = "failed"
        doc.error = str(e)
        session.add(doc)
        session.commit()
        # Missing API key / misconfiguration is a client-fixable 400; an actual
        # upstream LLM failure is a 502.
        status = 400 if isinstance(e, MissingProviderKey) else 502
        raise HTTPException(status, str(e)) from e

    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _to_read(doc)


@router.get("", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_session)) -> list[DocumentRead]:
    docs = session.exec(select(Document).order_by(Document.created_at.desc())).all()
    return [_to_read(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: uuid.UUID, session: Session = Depends(get_session)) -> DocumentRead:
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(404, f"document {document_id} not found")
    return _to_read(doc)


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document_items(
    document_id: uuid.UUID, payload: DocumentItemsUpdate, session: Session = Depends(get_session)
) -> DocumentRead:
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(404, f"document {document_id} not found")
    if doc.status == "confirmed":
        raise HTTPException(409, "document already confirmed, cannot edit")
    doc.parsed_response = {"items": [i.model_dump(mode="json") for i in payload.items]}
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _to_read(doc)


@router.post("/{document_id}/confirm", response_model=list[str])
def confirm_document(
    document_id: uuid.UUID,
    mode: Literal["replace", "merge"] = Query(default="merge"),
    session: Session = Depends(get_session),
) -> list[str]:
    """Commit a document's parsed items to the live menu. Returns committed ids."""
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(404, f"document {document_id} not found")
    if doc.status == "confirmed":
        raise HTTPException(409, "document already confirmed")

    items = [DraftMenuItem.model_validate(i) for i in doc.parsed_response.get("items", [])]
    if mode == "replace":
        session.exec(delete(MenuItem))

    committed: list[str] = []
    for item in items:
        item_id = item.id or slugify(item.name)
        existing = session.get(MenuItem, item_id)
        target = existing or MenuItem(id=item_id)
        target.branch_id = item.branch_id or doc.branch_id
        target.name = item.name
        target.category = item.category
        target.description = item.description
        target.available = item.available
        target.voice_alias = item.voice_alias
        target.image_url = item.image_url
        target.calories = item.calories
        target.price = item.price
        target.currency = item.currency
        target.sizes = [
            MenuItemSize(size=s.size, price=s.price, calories=s.calories) for s in item.sizes
        ]
        session.add(target)
        committed.append(item_id)

    doc.status = "confirmed"
    session.add(doc)
    session.commit()
    return committed


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, session: Session = Depends(get_session)) -> None:
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(404, f"document {document_id} not found")
    session.delete(doc)
    session.commit()
