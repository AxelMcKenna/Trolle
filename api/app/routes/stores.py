from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.db.session import get_async_session
from app.schemas.products import StoreListResponse
from app.schemas.rankings import StoreRankingResponse
from app.services.rankings import VALID_CATEGORIES, rank_stores_by_category
from app.services.search import fetch_stores_nearby

router = APIRouter(prefix="/stores", tags=["stores"])
settings = get_settings()


@router.get("/rankings")
async def store_rankings(
    category: str = Query(...),
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(5.0),
) -> StoreRankingResponse:
    if not (-47 <= lat <= -34):
        raise HTTPException(status_code=400, detail="Latitude must be within New Zealand bounds (-47 to -34)")
    if not (165 <= lon <= 179):
        raise HTTPException(status_code=400, detail="Longitude must be within New Zealand bounds (165 to 179)")
    if radius_km <= 0:
        raise HTTPException(status_code=400, detail="radius_km must be positive")
    if radius_km > 10:
        raise HTTPException(status_code=400, detail="Search radius cannot exceed 10km")
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}")

    async with get_async_session() as session:
        return await rank_stores_by_category(session, category, lat, lon, radius_km)


@router.get("")
async def stores_nearby(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float | None = Query(None),
) -> StoreListResponse:
    async with get_async_session() as session:
        radius = radius_km if radius_km is not None else settings.default_radius_km
        if radius <= 0:
            raise HTTPException(status_code=400, detail="radius_km must be positive")
        if radius > 10:
            raise HTTPException(status_code=400, detail="Search radius cannot exceed 10km")
        return await fetch_stores_nearby(session, lat=lat, lon=lon, radius_km=radius)
