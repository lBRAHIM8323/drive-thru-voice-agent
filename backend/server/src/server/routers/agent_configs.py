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
from ..deps import get_current_user, require_branch_resource
from ..models import AgentConfigRecord, User
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
def list_configs(
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    _user: User = Depends(get_current_user),
) -> list[AgentConfigSummary]:
    stmt = select(AgentConfigRecord)
    if user_branch_id is not None:
        stmt = stmt.where(
            (AgentConfigRecord.branch_id == user_branch_id)
            | (AgentConfigRecord.branch_id.is_(None))
        )
    return [_summary(r) for r in session.exec(stmt).all()]


@router.post("", response_model=AgentConfigSummary, status_code=201)
def create_config(
    payload: AgentConfigCreate,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    user: User = Depends(get_current_user),
) -> AgentConfigSummary:
    if user.role not in ("admin", "manager"):
        raise HTTPException(403, "Only admin and manager can create agent configs")
    config_id = payload.id or uuid.uuid4().hex
    if session.get(AgentConfigRecord, config_id):
        raise HTTPException(409, f"agent config {config_id!r} already exists")
    branch_id = payload.branch_id
    if user_branch_id is not None:
        if branch_id is not None and branch_id != user_branch_id:
            raise HTTPException(403, "Cannot create config for another branch")
        branch_id = user_branch_id
    rec = AgentConfigRecord(
        id=config_id,
        name=payload.name,
        branch_id=branch_id,
        is_active=payload.is_active,
        config=payload.config.model_dump(),
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return _summary(rec)


@router.get("/{config_id}", response_model=AgentConfig)
def get_config(
    config_id: str,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    _user: User = Depends(get_current_user),
) -> AgentConfig:
    """Return the bare AgentConfig payload the voice-agent consumes."""
    rec = session.get(AgentConfigRecord, config_id)
    if not rec:
        raise HTTPException(404, f"agent config {config_id!r} not found")
    if user_branch_id is not None and rec.branch_id is not None and rec.branch_id != user_branch_id:
        raise HTTPException(403, "Access denied to this agent config")
    return AgentConfig.model_validate(rec.config)


@router.patch("/{config_id}", response_model=AgentConfigSummary)
def update_config(
    config_id: str,
    payload: AgentConfigUpdate,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    user: User = Depends(get_current_user),
) -> AgentConfigSummary:
    rec = session.get(AgentConfigRecord, config_id)
    if not rec:
        raise HTTPException(404, f"agent config {config_id!r} not found")
    if user.role != "admin":
        if user_branch_id is None or rec.branch_id != user_branch_id:
            raise HTTPException(403, "Access denied to this agent config")
        if payload.branch_id is not None and payload.branch_id != user_branch_id:
            raise HTTPException(403, "Cannot reassign config to another branch")
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
def delete_config(
    config_id: str,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    user: User = Depends(get_current_user),
) -> None:
    rec = session.get(AgentConfigRecord, config_id)
    if not rec:
        raise HTTPException(404, f"agent config {config_id!r} not found")
    if user.role != "admin":
        if user_branch_id is None or rec.branch_id != user_branch_id:
            raise HTTPException(403, "Access denied to this agent config")
    session.delete(rec)
    session.commit()
