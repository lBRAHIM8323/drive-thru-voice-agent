"""Session listing, detail, and lifecycle — admin/manager scoped."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session as DbSession, select

from ..db import get_session
from ..deps import get_current_user, require_branch_resource, require_role, verify_agent_api_key
from ..models import Order, OrderItem, Session, User
from ..schemas.session import OrderItemRead, OrderRead, SessionRead

router = APIRouter(prefix="/sessions", tags=["sessions"])


class HandoffNote(BaseModel):
    text: str
    at: str | None = None


class HandoffEpisodeIn(BaseModel):
    """A recorded human-takeover episode: why it happened and what was said while
    the human handled the customer (the agent observes and notes this so the
    resolution can be reviewed and learned from)."""

    reason: str | None = None
    notes: list[HandoffNote] = Field(default_factory=list)


def _build_session_read(session: Session) -> SessionRead:
    return SessionRead(
        id=session.id,
        branch_id=session.branch_id,
        agent_config_id=session.agent_config_id,
        room_name=session.room_name,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        audio_url=session.audio_url,
        transcript=session.transcript,
        orders=[
            OrderRead(
                id=o.id,
                session_id=o.session_id,
                branch_id=o.branch_id,
                status=o.status,
                subtotal=o.subtotal,
                tax=o.tax,
                total=o.total,
                currency=o.currency,
                placed_at=o.placed_at,
                created_at=o.created_at,
                updated_at=o.updated_at,
                items=[
                    OrderItemRead(
                        id=i.id,
                        order_id=i.order_id,
                        menu_item_id=i.menu_item_id,
                        name_snapshot=i.name_snapshot,
                        size=i.size,
                        quantity=i.quantity,
                        unit_price=i.unit_price,
                        total_price=i.total_price,
                        notes=i.notes,
                    )
                    for i in (o.items or [])
                ],
            )
            for o in (session.orders or [])
        ],
    )


@router.get("", response_model=list[SessionRead])
def list_sessions(
    session: DbSession = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    _user: User = Depends(get_current_user),
) -> list[SessionRead]:
    stmt = select(Session).order_by(Session.started_at.desc())
    if user_branch_id is not None:
        stmt = stmt.where(Session.branch_id == user_branch_id)
    results = session.exec(stmt).all()
    return [_build_session_read(s) for s in results]


@router.get("/{session_id}", response_model=SessionRead)
def get_session_by_id(
    session_id: uuid.UUID,
    session: DbSession = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    _user: User = Depends(get_current_user),
) -> SessionRead:
    sess = session.get(Session, session_id)
    if not sess:
        raise HTTPException(404, f"session {session_id} not found")
    if user_branch_id is not None and sess.branch_id != user_branch_id:
        raise HTTPException(403, "Access denied to this session")
    return _build_session_read(sess)


@router.patch("/by-room/{room_name}/complete")
def complete_session_by_room(
    room_name: str,
    session: DbSession = Depends(get_session),
    _verified: None = Depends(verify_agent_api_key),
) -> dict[str, str]:
    sess = session.exec(select(Session).where(Session.room_name == room_name)).first()
    if not sess:
        raise HTTPException(404, f"session with room {room_name!r} not found")
    sess.status = "completed"
    sess.ended_at = datetime.now(timezone.utc)
    session.add(sess)
    session.commit()
    return {"status": "completed", "session_id": str(sess.id)}


@router.post("/by-room/{room_name}/handoff-notes")
def add_handoff_notes(
    room_name: str,
    payload: HandoffEpisodeIn,
    session: DbSession = Depends(get_session),
    _verified: None = Depends(verify_agent_api_key),
) -> dict[str, object]:
    """Append a human-handoff episode (reason + observed notes) to the session.

    Stored under ``transcript['handoff_episodes']`` so managers can review what a
    human did when the agent handed off — the seed of a learning loop.
    """
    sess = session.exec(select(Session).where(Session.room_name == room_name)).first()
    if not sess:
        raise HTTPException(404, f"session with room {room_name!r} not found")

    # JSON column: build a fresh dict so SQLAlchemy detects the change.
    transcript = dict(sess.transcript or {})
    episodes = list(transcript.get("handoff_episodes", []))
    episodes.append(
        {
            "reason": payload.reason,
            "notes": [n.model_dump() for n in payload.notes],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    transcript["handoff_episodes"] = episodes
    sess.transcript = transcript
    session.add(sess)
    session.commit()
    return {"status": "ok", "episodes": len(episodes)}
