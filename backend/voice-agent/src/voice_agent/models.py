"""Factory that turns an :class:`AgentConfig` into LiveKit plugin instances.

Provider plugins are imported lazily inside each branch so that selecting one
provider never requires the others to import cleanly, and so startup isn't slowed
by importing every SDK. API keys are read from the environment by the plugins
themselves — they are never sourced from the config.
"""

from __future__ import annotations

from typing import Any

from livekit.agents import llm as llm_lib
from livekit.agents import stt as stt_lib
from livekit.agents import tts as tts_lib
from livekit.agents import vad as vad_lib

from .config import (
    LLMConfig,
    STTConfig,
    TTSConfig,
    TurnDetectionConfig,
    VADConfig,
)


def _clean(**kwargs: Any) -> dict[str, Any]:
    """Drop keys whose value is None so plugin defaults stay intact."""
    return {k: v for k, v in kwargs.items() if v is not None}


def build_stt(cfg: STTConfig) -> stt_lib.STT:
    if cfg.provider == "deepgram":
        from livekit.plugins import deepgram

        return deepgram.STT(
            **_clean(
                model=cfg.model,
                language=cfg.language,
                keyterm=cfg.keyterms or None,
            ),
            **cfg.extra,
        )
    if cfg.provider == "assemblyai":
        from livekit.plugins import assemblyai

        return assemblyai.STT(**_clean(model=cfg.model), **cfg.extra)
    raise ValueError(f"Unsupported STT provider: {cfg.provider!r}")


def build_llm(cfg: LLMConfig) -> llm_lib.LLM:
    common = _clean(
        model=cfg.model,
        temperature=cfg.temperature,
        parallel_tool_calls=cfg.parallel_tool_calls,
    )
    if cfg.provider == "openai":
        from livekit.plugins import openai

        return openai.LLM(**common, **cfg.extra)
    if cfg.provider == "anthropic":
        from livekit.plugins import anthropic

        return anthropic.LLM(**common, **cfg.extra)
    if cfg.provider == "google":
        from livekit.plugins import google

        # google.LLM has no parallel_tool_calls kwarg.
        common.pop("parallel_tool_calls", None)
        return google.LLM(**common, **cfg.extra)
    raise ValueError(f"Unsupported LLM provider: {cfg.provider!r}")


def build_tts(cfg: TTSConfig) -> tts_lib.TTS:
    if cfg.provider == "cartesia":
        from livekit.plugins import cartesia

        return cartesia.TTS(
            **_clean(model=cfg.model, voice=cfg.voice, language=cfg.language),
            **cfg.extra,
        )
    if cfg.provider == "elevenlabs":
        from livekit.plugins import elevenlabs

        # ElevenLabs uses `voice_id` rather than `voice`.
        return elevenlabs.TTS(
            **_clean(model=cfg.model, voice_id=cfg.voice, language=cfg.language),
            **cfg.extra,
        )
    raise ValueError(f"Unsupported TTS provider: {cfg.provider!r}")


def build_vad(cfg: VADConfig) -> vad_lib.VAD | None:
    if not cfg.enabled:
        return None
    from livekit.plugins import silero

    return silero.VAD.load(
        **_clean(
            min_speech_duration=cfg.min_speech_duration,
            min_silence_duration=cfg.min_silence_duration,
            activation_threshold=cfg.activation_threshold,
        )
    )


def build_turn_detection(cfg: TurnDetectionConfig):
    """Return a turn-detection model/string for AgentSession, or None.

    "multilingual"/"english" use the LiveKit cloud EOU model (requires
    LIVEKIT_API_KEY/SECRET to be set — falls back to VAD if unreachable);
    "vad"/"stt" return the literal mode string the session understands;
    "none" disables turn detection.
    """
    if cfg.mode in ("multilingual", "english"):
        from livekit.agents.inference import TurnDetector

        return TurnDetector()
    if cfg.mode in ("vad", "stt"):
        return cfg.mode
    return None
