"""Mint a LiveKit connection token for the customer-facing page.

The room is pre-created with metadata ``{"config_id": ...}`` so the
(auto-dispatched) voice-agent reads it via room-metadata fallback and fetches
the right AgentConfig. Also returns the UI/appearance settings so the customer
page can render the admin-selected visualizer.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from livekit import api
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import get_session
from ..models import AgentConfigRecord, Session as SessionRecord
from ..schemas.agent_config import UIConfig
from ..settings import get_settings

router = APIRouter(prefix="/connection", tags=["connection"])


class ConnectionRequest(BaseModel):
    config_id: str | None = None  # defaults to the active config


class ConnectionInfo(BaseModel):
    server_url: str
    token: str
    room_name: str
    identity: str
    config_id: str
    ui: UIConfig


def _client_ws_url(url: str) -> str:
    """The browser client needs a ws(s):// URL; the HTTP API uses http(s)://."""
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url  # already ws:// or wss://


def _resolve_config(session: Session, config_id: str | None) -> AgentConfigRecord:
    if config_id:
        rec = session.get(AgentConfigRecord, config_id)
        if not rec:
            raise HTTPException(404, f"agent config {config_id!r} not found")
        return rec
    rec = session.exec(
        select(AgentConfigRecord)
        .where(AgentConfigRecord.is_active == True)  # noqa: E712
        .order_by(AgentConfigRecord.updated_at.desc())
    ).first()
    if not rec:
        raise HTTPException(409, "no active agent config; activate one in the admin panel")
    return rec


@router.post("", response_model=ConnectionInfo)
async def create_connection(
    body: ConnectionRequest | None = None,
    session: Session = Depends(get_session),
) -> ConnectionInfo:
    settings = get_settings()
    if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
        raise HTTPException(503, "LiveKit is not configured (set LIVEKIT_URL/API_KEY/API_SECRET)")

    rec = _resolve_config(session, body.config_id if body else None)
    ui = UIConfig.model_validate((rec.config or {}).get("ui") or {})

    room_name = f"drivethru-{uuid.uuid4().hex[:10]}"
    identity = f"customer-{uuid.uuid4().hex[:8]}"

    # Embed config_id as room metadata directly in the token's RoomConfiguration.
    # The room is auto-created (with this metadata) when the customer joins, and
    # the auto-dispatched agent reads it via its room-metadata fallback. This
    # avoids any server->LiveKit HTTP API call (which a reverse proxy may not
    # expose) — the only LiveKit dependency is the browser's wss connection.
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name("Customer")
        .with_grants(
            api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True)
        )
        .with_room_config(
            api.RoomConfiguration(
                metadata=json.dumps({"config_id": rec.id}),
                empty_timeout=300,
            )
        )
        .to_jwt()
    )

    db_session_obj = SessionRecord(
        branch_id=rec.branch_id,
        agent_config_id=rec.id,
        room_name=room_name,
    )
    session.add(db_session_obj)
    session.commit()

    return ConnectionInfo(
        server_url=_client_ws_url(settings.livekit_url),
        token=token,
        room_name=room_name,
        identity=identity,
        config_id=rec.id,
        ui=ui,
    )
