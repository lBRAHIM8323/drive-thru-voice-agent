"""Per-provider LLM adapters that turn menu text/images into structured items.

Each adapter returns a list of ``DraftMenuItem``. API keys are read by the SDKs
from the environment — never from the request. SDK clients are imported lazily so
an unused/unconfigured provider never blocks startup.
"""

from __future__ import annotations

import base64
import json
import os
import re

from pydantic import BaseModel

from ..schemas.menu import DraftMenuItem


class ParserError(Exception):
    """Raised when an LLM call fails or returns unparseable output."""


class MissingProviderKey(ParserError):
    """Raised when the selected provider's API key isn't configured."""


# Env var(s) that hold each provider's API key.
PROVIDER_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
}


def require_provider_key(provider: str) -> None:
    """Raise MissingProviderKey if the provider has no API key in the env."""
    keys = PROVIDER_ENV_KEYS.get(provider, ())
    if keys and not any(os.getenv(k) for k in keys):
        raise MissingProviderKey(
            f"{' or '.join(keys)} is not set. Set it in the server environment, "
            f"or switch the parser provider via PUT /api/v1/parser-config."
        )


class ParsedMenu(BaseModel):
    items: list[DraftMenuItem]


_MAX_TOKENS = 8192


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction from a model's text response."""
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} span.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _validate(data: dict) -> list[DraftMenuItem]:
    return ParsedMenu.model_validate(data).items


# --- OpenAI ---------------------------------------------------------------


def openai_parse(
    *, model: str, system: str, temperature: float | None,
    text: str | None = None, image_bytes: bytes | None = None, image_mime: str | None = None,
) -> list[DraftMenuItem]:
    from openai import OpenAI

    client = OpenAI()
    if image_bytes is not None:
        b64 = base64.b64encode(image_bytes).decode()
        user_content = [
            {"type": "text", "text": "Extract the menu from this image."},
            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{b64}"}},
        ]
    else:
        user_content = text or ""

    kwargs = {"temperature": temperature} if temperature is not None else {}
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            **kwargs,
        )
        return _validate(_extract_json(resp.choices[0].message.content or ""))
    except Exception as e:  # noqa: BLE001
        raise ParserError(f"OpenAI parse failed: {e}") from e


# --- Anthropic ------------------------------------------------------------


def anthropic_parse(
    *, model: str, system: str, temperature: float | None,
    text: str | None = None, image_bytes: bytes | None = None, image_mime: str | None = None,
) -> list[DraftMenuItem]:
    import anthropic

    client = anthropic.Anthropic()
    if image_bytes is not None:
        b64 = base64.b64encode(image_bytes).decode()
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": image_mime, "data": b64}},
            {"type": "text", "text": "Extract the menu from this image."},
        ]
    else:
        content = text or ""

    kwargs = {"temperature": temperature} if temperature is not None else {}
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": content}],
            **kwargs,
        )
        out = "".join(block.text for block in msg.content if block.type == "text")
        return _validate(_extract_json(out))
    except Exception as e:  # noqa: BLE001
        raise ParserError(f"Anthropic parse failed: {e}") from e


# --- Google (Gemini) ------------------------------------------------------


def google_parse(
    *, model: str, system: str, temperature: float | None,
    text: str | None = None, image_bytes: bytes | None = None, image_mime: str | None = None,
) -> list[DraftMenuItem]:
    from google import genai
    from google.genai import types

    client = genai.Client()
    if image_bytes is not None:
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime or "image/png"),
            "Extract the menu from this image.",
        ]
    else:
        contents = [text or ""]

    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        **({"temperature": temperature} if temperature is not None else {}),
    )
    try:
        resp = client.models.generate_content(model=model, contents=contents, config=config)
        return _validate(_extract_json(resp.text or ""))
    except Exception as e:  # noqa: BLE001
        raise ParserError(f"Google parse failed: {e}") from e


PROVIDERS = {
    "openai": openai_parse,
    "anthropic": anthropic_parse,
    "google": google_parse,
}
