"""User registration and authentication (JWT access + rotating refresh)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.config import get_settings
from smithy_cloud.database import get_db
from smithy_cloud.deps import get_current_user, require_level
from smithy_cloud.models import RefreshToken, User
from smithy_cloud.schemas import RefreshRequest, RegisterRequest, TokenPair, UserResponse
from smithy_cloud.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_pair(user: User, db: AsyncSession) -> TokenPair:
    settings = get_settings()
    raw, digest = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=digest,
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        )
    )
    await db.commit()
    return TokenPair(
        access_token=create_access_token(user_id=str(user.id), role=user.role),
        refresh_token=raw,
    )


@router.post("/register", response_model=TokenPair, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    """Register a user. First user in an empty table becomes admin."""
    settings = get_settings()
    total = await db.scalar(select(func.count()).select_from(User))
    if total and total > 0 and not settings.REGISTRATION_OPEN:
        raise HTTPException(status_code=403, detail="Registration is closed")
    role = "admin" if not total else "viewer"
    user = User(email=body.email, password_hash=hash_password(body.password), role=role)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered") from err
    return await _issue_pair(user, db)


@router.post("/login", response_model=TokenPair)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    """OAuth2 password flow — ``username`` carries the email."""
    result = await db.execute(select(User).where(User.email == form.username.strip().lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is deactivated")
    return await _issue_pair(user, db)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    """Rotate a refresh token. Reuse of a revoked token nukes the whole family."""
    digest = hash_refresh_token(body.refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == digest))
    stored = result.scalar_one_or_none()
    if stored is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if stored.revoked or stored.expires_at <= datetime.now(UTC):
        # Possible theft — revoke everything issued to this user.
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == stored.user_id)
            .values(revoked=True)
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    stored.revoked = True
    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return await _issue_pair(user, db)


@router.get("/me", response_model=UserResponse)
async def me(user: User | None = Depends(require_level("viewer"))) -> User:
    if user is None:  # auth disabled — no identity to report.
        raise HTTPException(status_code=401, detail="Authentication is disabled")
    return user


@router.get("/status")
async def auth_status() -> dict[str, bool]:
    """Public: lets the SPA/CLI know whether user auth is enforced."""
    return {"auth_enabled": get_settings().AUTH_ENABLED}


@router.post("/logout")
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Revoke one refresh token (idempotent)."""
    digest = hash_refresh_token(body.refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == digest))
    stored = result.scalar_one_or_none()
    if stored is not None and not stored.revoked:
        stored.revoked = True
        await db.commit()
    return {"status": "ok"}


# Re-exported for route modules that only need the dependency.
current_user = get_current_user
