"""Named key-value assets: CRUD + immutable lock against update/delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.database import get_db
from smithy_cloud.deps import require_level
from smithy_cloud.models import Asset, User
from smithy_cloud.schemas import AssetCreate, AssetResponse, AssetUpdate

router = APIRouter(tags=["assets"])


async def _get_asset_or_404(name: str, db: AsyncSession) -> Asset:
    result = await db.execute(select(Asset).where(Asset.name == name))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.post("/assets", response_model=AssetResponse, status_code=201)
async def create_asset(
    body: AssetCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> Asset:
    """Create an asset; duplicate names are rejected with 409."""
    result = await db.execute(select(Asset).where(Asset.name == body.name))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Asset already exists")
    asset = Asset(name=body.name, value=body.value, immutable=body.immutable)
    db.add(asset)
    try:
        await db.commit()
    except IntegrityError:
        # Lost a creation race — the winner owns the name.
        await db.rollback()
        raise HTTPException(status_code=409, detail="Asset already exists") from None
    await db.refresh(asset)
    return asset


@router.get("/assets", response_model=list[AssetResponse])
async def list_assets(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(require_level("viewer")),
) -> list[Asset]:
    result = await db.execute(
        select(Asset).order_by(Asset.name).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/assets/{name}", response_model=AssetResponse)
async def get_asset(
    name: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("viewer")),
) -> Asset:
    return await _get_asset_or_404(name, db)


@router.patch("/assets/{name}", response_model=AssetResponse)
async def update_asset(
    name: str,
    body: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> Asset:
    """Update value and/or lock immutable; immutable rows reject any change."""
    asset = await _get_asset_or_404(name, db)
    if asset.immutable:
        raise HTTPException(status_code=409, detail="Asset is immutable")
    if body.value is not None:
        asset.value = body.value
    if body.immutable is not None:
        asset.immutable = body.immutable
    await db.commit()
    await db.refresh(asset)
    return asset


@router.delete("/assets/{name}", status_code=204)
async def delete_asset(
    name: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> None:
    """Delete an asset; immutable rows are protected."""
    asset = await _get_asset_or_404(name, db)
    if asset.immutable:
        raise HTTPException(status_code=409, detail="Asset is immutable")
    await db.delete(asset)
    await db.commit()
