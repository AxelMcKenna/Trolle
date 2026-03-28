from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, cast, func, select
from geoalchemy2 import Geography

from app.core.config import get_settings
from app.db.models import DeliverySlot, Store
from app.db.session import get_async_session
from app.schemas.fulfillment import (
    NearbySlotResponse,
    NearbyStoreSlotSummary,
    SlotAvailability,
    SlotDetail,
    StoreSlotResponse,
)
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


@router.get("/{store_id}/slots")
async def store_slots(store_id: UUID) -> StoreSlotResponse:
    """Get delivery and click-and-collect slot availability for a specific store."""
    now = datetime.now(tz=timezone.utc)

    async with get_async_session() as session:
        # Load store
        result = await session.execute(select(Store).where(Store.id == store_id))
        store = result.scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")

        # Load future slots
        slot_query = (
            select(DeliverySlot)
            .where(
                and_(
                    DeliverySlot.store_id == store_id,
                    DeliverySlot.slot_start >= now,
                )
            )
            .order_by(DeliverySlot.slot_start)
        )
        slot_result = await session.execute(slot_query)
        slots = slot_result.scalars().all()

        # Group by fulfillment type
        delivery_slots: list[SlotDetail] = []
        cc_slots: list[SlotDetail] = []

        for slot in slots:
            detail = SlotDetail(
                slot_date=slot.slot_date,
                slot_start=slot.slot_start,
                slot_end=slot.slot_end,
                is_available=slot.is_available,
                price_nzd=slot.price_nzd,
            )
            if slot.fulfillment_type == "delivery":
                delivery_slots.append(detail)
            elif slot.fulfillment_type == "click_collect":
                cc_slots.append(detail)

        def _build_availability(slot_list: list[SlotDetail], ft: str) -> SlotAvailability | None:
            if not slot_list:
                return None
            available = [s for s in slot_list if s.is_available]
            return SlotAvailability(
                fulfillment_type=ft,
                has_slots_available=len(available) > 0,
                next_available_slot=available[0].slot_start if available else None,
                slots=slot_list,
            )

        return StoreSlotResponse(
            store_id=store.id,
            store_name=store.name,
            chain=store.chain,
            delivery_slots=_build_availability(delivery_slots, "delivery"),
            click_collect_slots=_build_availability(cc_slots, "click_collect"),
        )


@router.get("/slots/nearby")
async def nearby_store_slots(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(5.0),
    fulfillment_type: str | None = Query(None),
) -> NearbySlotResponse:
    """Get slot availability summary for nearby stores.

    Optionally filter by fulfillment_type ("delivery" or "click_collect").
    """
    if not (-47 <= lat <= -34):
        raise HTTPException(status_code=400, detail="Latitude must be within New Zealand bounds (-47 to -34)")
    if not (165 <= lon <= 179):
        raise HTTPException(status_code=400, detail="Longitude must be within New Zealand bounds (165 to 179)")
    if radius_km > 10:
        raise HTTPException(status_code=400, detail="Search radius cannot exceed 10km")
    if fulfillment_type and fulfillment_type not in ("delivery", "click_collect"):
        raise HTTPException(status_code=400, detail="fulfillment_type must be 'delivery' or 'click_collect'")

    now = datetime.now(tz=timezone.utc)

    async with get_async_session() as session:
        user_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        user_point_geog = cast(user_point, Geography)
        radius_m = radius_km * 1000

        distance_m = func.ST_Distance(Store.geog, user_point_geog).label("distance_m")
        store_query = (
            select(Store, distance_m)
            .where(Store.geog.is_not(None))
            .where(func.ST_DWithin(Store.geog, user_point_geog, radius_m))
            .order_by(distance_m)
        )

        # Filter by fulfillment capability
        if fulfillment_type == "delivery":
            store_query = store_query.where(Store.delivery != False)  # noqa: E712
        elif fulfillment_type == "click_collect":
            store_query = store_query.where(Store.click_collect != False)  # noqa: E712

        store_result = await session.execute(store_query)
        stores = store_result.all()

        if not stores:
            return NearbySlotResponse(items=[])

        store_ids = [s.id for s, _ in stores]

        # Batch query: next available slot per store per fulfillment type
        slot_query = (
            select(
                DeliverySlot.store_id,
                DeliverySlot.fulfillment_type,
                func.min(DeliverySlot.slot_start).label("next_slot"),
            )
            .where(
                and_(
                    DeliverySlot.store_id.in_(store_ids),
                    DeliverySlot.is_available == True,  # noqa: E712
                    DeliverySlot.slot_start >= now,
                )
            )
            .group_by(DeliverySlot.store_id, DeliverySlot.fulfillment_type)
        )
        slot_result = await session.execute(slot_query)

        # Index: (store_id, fulfillment_type) -> next_slot
        slot_index: dict[tuple, datetime] = {}
        for row in slot_result.all():
            slot_index[(row.store_id, row.fulfillment_type)] = row.next_slot

        items = []
        for store, distance in stores:
            next_del = slot_index.get((store.id, "delivery"))
            next_cc = slot_index.get((store.id, "click_collect"))

            items.append(NearbyStoreSlotSummary(
                store_id=store.id,
                store_name=store.name,
                chain=store.chain,
                distance_km=round(distance / 1000, 2),
                delivery_available=next_del is not None if store.delivery is not False else False,
                cc_available=next_cc is not None if store.click_collect is not False else False,
                next_delivery_slot=next_del,
                next_cc_slot=next_cc,
            ))

        return NearbySlotResponse(items=items)
