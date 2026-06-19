"""Password hashing utilities (bcrypt)."""

from __future__ import annotations

import bcrypt

# bcrypt operates on the first 72 bytes of the password.
_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:_MAX_BYTES], hashed.encode("utf-8"))
    except ValueError:
        return False
