"""Password hashing (bcrypt) and token helpers for user auth.

Access tokens are short-lived JWTs (HS256); refresh tokens are opaque
random strings of which only the sha256 hash is stored — the same
convention as agent secrets.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from smithy_cloud.config import get_settings


class InvalidTokenError(ValueError):
    """Raised when an access token is missing, malformed, or expired."""


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(*, user_id: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MIN),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as err:
        raise InvalidTokenError(str(err)) from err
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("role"), str):
        raise InvalidTokenError("Token payload missing sub/role")
    return dict(payload)


def new_refresh_token() -> tuple[str, str]:
    """Return ``(raw_token, sha256_hash)`` — only the hash goes to the DB."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
