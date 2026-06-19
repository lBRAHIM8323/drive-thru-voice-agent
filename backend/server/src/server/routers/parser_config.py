"""Admin-configurable menu parser settings (which LLM parses uploads)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..db import get_session
from ..models import ParserConfigRecord
from ..schemas.menu import ParserConfigRead, ParserConfigUpdate

router = APIRouter(prefix="/parser-config", tags=["parser-config"])


def _get_or_create(session: Session) -> ParserConfigRecord:
    cfg = session.get(ParserConfigRecord, 1)
    if cfg is None:
        cfg = ParserConfigRecord()
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    return cfg


@router.get("", response_model=ParserConfigRead)
def get_parser_config(session: Session = Depends(get_session)) -> ParserConfigRead:
    return ParserConfigRead.model_validate(_get_or_create(session), from_attributes=True)


@router.put("", response_model=ParserConfigRead)
def update_parser_config(
    payload: ParserConfigUpdate, session: Session = Depends(get_session)
) -> ParserConfigRead:
    cfg = _get_or_create(session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return ParserConfigRead.model_validate(cfg, from_attributes=True)
