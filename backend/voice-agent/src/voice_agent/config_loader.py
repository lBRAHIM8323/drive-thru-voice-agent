"""Resolve the per-session :class:`AgentConfig` at runtime.

Resolution order (first match wins):

1. ``{"config": {...}}`` in the job/room metadata — an inline config, mostly for
   testing and local dispatch.
2. ``{"config_id": "..."}`` in the metadata — fetched from ``backend/server`` at
   ``GET {SERVER_URL}/agent/agent-configs/{config_id}``.
3. Anything missing or failing falls back to :meth:`AgentConfig.default`, so the
   agent always starts (useful before the server exists).
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from livekit.agents import JobContext

from .config import AgentConfig

logger = logging.getLogger("drive-thru.config")

CONFIG_PATH = "/agent/agent-configs/{config_id}"
_FETCH_TIMEOUT = 10.0


def _read_metadata(ctx: JobContext) -> dict:
    """Parse JSON metadata from the job, falling back to the room."""
    for source in (getattr(ctx.job, "metadata", None), getattr(ctx.room, "metadata", None)):
        if not source:
            continue
        try:
            data = json.loads(source)
        except (json.JSONDecodeError, TypeError):
            logger.warning("ignoring non-JSON metadata: %r", source)
            continue
        if isinstance(data, dict):
            return data
    return {}


async def _fetch_config(config_id: str) -> AgentConfig:
    server_url = os.getenv("SERVER_URL")
    if not server_url:
        raise RuntimeError("SERVER_URL is not set; cannot fetch config by id")

    url = server_url.rstrip("/") + CONFIG_PATH.format(config_id=config_id)
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return AgentConfig.model_validate(resp.json())


async def load_agent_config(ctx: JobContext) -> AgentConfig:
    """Resolve the session config, never raising — falls back to defaults."""
    metadata = _read_metadata(ctx)

    if isinstance(metadata.get("config"), dict):
        try:
            config = AgentConfig.model_validate(metadata["config"])
            logger.info("loaded inline config from metadata")
            return config
        except Exception:
            logger.exception("invalid inline config in metadata; using default")
            return AgentConfig.default()

    config_id = metadata.get("config_id")
    if config_id:
        try:
            config = await _fetch_config(str(config_id))
            logger.info("loaded config %s from server", config_id)
            return config
        except Exception:
            logger.exception("failed to fetch config %s; using default", config_id)
            return AgentConfig.default()

    logger.info("no config in metadata; using default config")
    return AgentConfig.default()
