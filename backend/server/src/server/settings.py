"""Environment-backed application settings."""

from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _build_database_url() -> str:
    """Prefer an explicit DATABASE_URL, else assemble one from POSTGRES_* parts."""
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
    db = os.getenv("POSTGRES_DB", "drive-thru-agent")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


class Settings:
    def __init__(self) -> None:
        self.database_url: str = _build_database_url()
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))

        # JWT
        self.jwt_secret: str = os.getenv("JWT_SECRET", "CHANGE-ME-IN-PRODUCTION-abcdef1234567890")
        self.jwt_algorithm: str = "HS256"
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

        # Optional bootstrap admin, seeded on init if both are set.
        self.admin_username: str | None = os.getenv("ADMIN_USERNAME")
        self.admin_password: str | None = os.getenv("ADMIN_PASSWORD")

        # Shared secret the voice-agent uses to authenticate with this API.
        self.agent_api_key: str | None = os.getenv("AGENT_API_KEY")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    # Provider keys are read by the SDKs from the environment directly; exposed
    # here only so endpoints can give a clear error when one is missing.
    @property
    def openai_api_key(self) -> str | None:
        return os.getenv("OPENAI_API_KEY")

    @property
    def anthropic_api_key(self) -> str | None:
        return os.getenv("ANTHROPIC_API_KEY")

    @property
    def google_api_key(self) -> str | None:
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    # LiveKit — used to mint connection tokens for the customer-facing page.
    @property
    def livekit_url(self) -> str | None:
        return os.getenv("LIVEKIT_URL")

    @property
    def livekit_api_key(self) -> str | None:
        return os.getenv("LIVEKIT_API_KEY")

    @property
    def livekit_api_secret(self) -> str | None:
        return os.getenv("LIVEKIT_API_SECRET")


@lru_cache
def get_settings() -> Settings:
    return Settings()
