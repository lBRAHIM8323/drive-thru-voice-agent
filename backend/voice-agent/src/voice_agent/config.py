"""Typed configuration schema for a drive-thru agent session.

This module defines the full surface the admin frontend can configure. It is the
JSON contract between ``backend/server`` (which stores/serves a config) and the
voice-agent (which fetches it at session start and builds the pipeline from it).

API keys are intentionally **not** part of this schema — the frontend only picks
providers, models and non-secret params; secrets live in the agent's environment
and are read directly by the plugins.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .database import COMMON_INSTRUCTIONS

STTProvider = Literal["deepgram", "assemblyai"]
LLMProvider = Literal["openai", "anthropic", "google"]
TTSProvider = Literal["cartesia", "elevenlabs"]
TurnDetectionMode = Literal["multilingual", "english", "vad", "stt", "none"]

# Defaults preserve the original hard-coded McDonald's behaviour so the agent
# keeps working when no server-side config is available.
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


class STTConfig(BaseModel):
    provider: STTProvider = "deepgram"
    model: str = "nova-3"
    language: str = "en"
    # Brand/keyword hints to bias transcription (Deepgram `keyterm`).
    keyterms: list[str] = Field(default_factory=lambda: list(DEFAULT_KEYTERMS))
    # Provider-specific passthrough kwargs (forwarded verbatim to the plugin).
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
    # For Cartesia this is the voice id; for ElevenLabs it maps to `voice_id`.
    voice: str | None = DEFAULT_CARTESIA_VOICE
    language: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class VADConfig(BaseModel):
    enabled: bool = True
    min_speech_duration: float | None = None
    min_silence_duration: float | None = None
    activation_threshold: float | None = None


class TurnDetectionConfig(BaseModel):
    # "multilingual"/"english" use the LiveKit EOU model; "vad"/"stt" use those
    # signals; "none" disables turn detection entirely.
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


class AgentConfig(BaseModel):
    """Full session configuration delivered per session from the server."""

    # System-prompt prefix. The runtime appends the menu sections to this.
    instructions: str = COMMON_INSTRUCTIONS
    # Optional opening line spoken/generated when the session starts.
    greeting: str | None = None

    stt: STTConfig = Field(default_factory=STTConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    turn_detection: TurnDetectionConfig = Field(default_factory=TurnDetectionConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    background_audio: BackgroundAudioConfig = Field(default_factory=BackgroundAudioConfig)

    @classmethod
    def default(cls) -> "AgentConfig":
        """The original hard-coded behaviour, used as a dev/no-server fallback."""
        return cls()
