"""Agent configuration CRUD.

`GET /agent-configs/{config_id}` returns the **bare** AgentConfig JSON — this is
the exact contract the voice-agent validates (see voice-agent/config_loader.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import AgentConfigRecord
from ..schemas.agent_config import (
    AgentConfig,
    AgentConfigCreate,
    AgentConfigSummary,
    AgentConfigUpdate,
)

router = APIRouter(prefix="/agent-configs", tags=["agent-configs"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _summary(rec: AgentConfigRecord) -> AgentConfigSummary:
    return AgentConfigSummary.model_validate(rec, from_attributes=True)


@router.get("", response_model=list[AgentConfigSummary])
def list_configs(session: Session = Depends(get_session)) -> list[AgentConfigSummary]:
    return [_summary(r) for r in session.exec(select(AgentConfigRecord)).all()]


@router.post("", response_model=AgentConfigSummary, status_code=201)
def create_config(
    payload: AgentConfigCreate, session: Session = Depends(get_session)
) -> AgentConfigSummary:
    config_id = payload.id or uuid.uuid4().hex
    if session.get(AgentConfigRecord, config_id):
        raise HTTPException(409, f"agent config {config_id!r} already exists")
    rec = AgentConfigRecord(
        id=config_id,
        name=payload.name,
        branch_id=payload.branch_id,
        is_active=payload.is_active,
        config=payload.config.model_dump(),
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return _summary(rec)


@router.get("/{config_id}", response_model=AgentConfig)
def get_config(config_id: str, session: Session = Depends(get_session)) -> AgentConfig:
    """Return the bare AgentConfig payload the voice-agent consumes."""
    rec = session.get(AgentConfigRecord, config_id)
    if not rec:
        raise HTTPException(404, f"agent config {config_id!r} not found")
    return AgentConfig.model_validate(rec.config)


@router.patch("/{config_id}", response_model=AgentConfigSummary)
def update_config(
    config_id: str, payload: AgentConfigUpdate, session: Session = Depends(get_session)
) -> AgentConfigSummary:
    rec = session.get(AgentConfigRecord, config_id)
    if not rec:
        raise HTTPException(404, f"agent config {config_id!r} not found")
    if payload.name is not None:
        rec.name = payload.name
    if payload.branch_id is not None:
        rec.branch_id = payload.branch_id
    if payload.is_active is not None:
        rec.is_active = payload.is_active
    if payload.config is not None:
        rec.config = payload.config.model_dump()
    rec.updated_at = _utcnow()
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return _summary(rec)


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: str, session: Session = Depends(get_session)) -> None:
    rec = session.get(AgentConfigRecord, config_id)
    if not rec:
        raise HTTPException(404, f"agent config {config_id!r} not found")
    session.delete(rec)
    session.commit()
