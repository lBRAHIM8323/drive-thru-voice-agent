"""AgentConfig schema — MIRROR of voice-agent's
``voice-agent/src/voice_agent/config.py``.

The two projects are separate uv packages; the JSON shape is the contract
between them. **Keep these models in sync** with the voice-agent. (Follow-up:
extract into a shared package so this duplication goes away.)

The server stores an ``AgentConfig`` payload as JSON and serves it verbatim at
``GET /api/v1/agent-configs/{id}``, which the voice-agent validates with
``AgentConfig.model_validate(resp.json())``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

STTProvider = Literal["deepgram", "assemblyai"]
LLMProvider = Literal["openai", "anthropic", "google"]
TTSProvider = Literal["cartesia", "elevenlabs"]
TurnDetectionMode = Literal["multilingual", "english", "vad", "stt", "none"]

DEFAULT_KEYTERMS = [
    "Big Mac",
    "McFlurry",
    "McCrispy",
    "McNuggets",
    "Meal",
    "Sundae",
    "Oreo",
    "Jalapeno Ranch",
]
DEFAULT_CARTESIA_VOICE = "f786b574-daa5-4673-aa0c-cbe3e8534c02"

# The voice-agent's COMMON_INSTRUCTIONS is the on-agent default. Here we keep a
# short placeholder; admins set the real prompt per config. The agent falls back
# to its own COMMON_INSTRUCTIONS when no config is found.
DEFAULT_INSTRUCTIONS = "You are a friendly drive-thru attendant. Keep replies short and natural."


class STTConfig(BaseModel):
    provider: STTProvider = "deepgram"
    model: str = "nova-3"
    language: str = "en"
    keyterms: list[str] = Field(default_factory=lambda: list(DEFAULT_KEYTERMS))
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    provider: LLMProvider = "openai"
    model: str = "gpt-4.1-mini"
    temperature: float | None = None
    parallel_tool_calls: bool | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class TTSConfig(BaseModel):
    provider: TTSProvider = "cartesia"
    model: str = "sonic-3"
    voice: str | None = DEFAULT_CARTESIA_VOICE
    language: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class VADConfig(BaseModel):
    enabled: bool = True
    min_speech_duration: float | None = None
    min_silence_duration: float | None = None
    activation_threshold: float | None = None


class TurnDetectionConfig(BaseModel):
    mode: TurnDetectionMode = "multilingual"


class SessionConfig(BaseModel):
    max_tool_steps: int = 10
    allow_interruptions: bool | None = None
    min_interruption_duration: float | None = None
    min_endpointing_delay: float | None = None
    max_endpointing_delay: float | None = None
    preemptive_generation: bool | None = None


class BackgroundAudioConfig(BaseModel):
    enabled: bool = True
    volume: float = 1.0


Visualizer = Literal["bar", "grid", "radial", "wave", "aura"]


class UIConfig(BaseModel):
    """Frontend appearance for the customer page. Ignored by the voice-agent."""

    visualizer: Visualizer = "bar"
    accent_color: str | None = None  # hex, e.g. "#e03131"
    title: str | None = None  # heading shown to the customer


class AgentConfig(BaseModel):
    """Full session configuration delivered to the voice-agent per session."""

    instructions: str = DEFAULT_INSTRUCTIONS
    greeting: str | None = None

    stt: STTConfig = Field(default_factory=STTConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    turn_detection: TurnDetectionConfig = Field(default_factory=TurnDetectionConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    background_audio: BackgroundAudioConfig = Field(default_factory=BackgroundAudioConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


# --- API wrappers (server-side metadata around the stored AgentConfig) ----


class AgentConfigCreate(BaseModel):
    id: str | None = None  # generated if omitted
    name: str = ""
    branch_id: uuid.UUID | None = None
    is_active: bool = False
    config: AgentConfig = Field(default_factory=AgentConfig)


class AgentConfigUpdate(BaseModel):
    name: str | None = None
    branch_id: uuid.UUID | None = None
    is_active: bool | None = None
    config: AgentConfig | None = None


class AgentConfigSummary(BaseModel):
    id: str
    name: str
    branch_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
