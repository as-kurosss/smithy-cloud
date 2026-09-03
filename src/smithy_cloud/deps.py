"""User-auth dependencies with role hierarchy.

Roles form a hierarchy (viewer < operator < admin); ``require_level``
gates a route at a minimum level. When ``AUTH_ENABLED=false`` every
dependency is a pass-through returning ``None`` so local dev and the
existing open behavior are untouched.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.config import get_settings
from smithy_cloud.database import get_db
from smithy_cloud.models import User
from smithy_cloud.security import InvalidTokenError, decode_access_token

ROLE_LEVELS: dict[str, int] = {"viewer": 1, "operator": 2, "admin": 3}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def _resolve_user(token: str | None, db: AsyncSession) -> User:
    """Validate a raw access token, raising 401 on any problem."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return the authenticated user, ``None`` when auth is disabled."""
    if not get_settings().AUTH_ENABLED:
        return None
    return await _resolve_user(token, db)


async def authorize_websocket(token: str | None, db: AsyncSession) -> User | None:
    """Validate a ``?token=`` access token for WebSocket handshakes.

    Browsers cannot set headers on WS connects, so the token travels in the
    query string and is checked with the same code. Returns ``None`` when
    auth is disabled; raises 401 otherwise.
    """
    if not get_settings().AUTH_ENABLED:
        return None
    return await _resolve_user(token, db)


def require_level(level: str) -> Callable[..., Coroutine[Any, Any, User | None]]:
    """Dependency factory: allow roles at or above ``level`` (403 below)."""

    async def _check(user: User | None = Depends(get_current_user)) -> User | None:
        if not get_settings().AUTH_ENABLED:
            return None
        if user is None:  # get_current_user raises when enabled; defensive.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )
        if ROLE_LEVELS.get(user.role, 0) < ROLE_LEVELS[level]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
            )
        return user

    return _check
