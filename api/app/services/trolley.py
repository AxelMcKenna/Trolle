from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography

from app.db.models import Price, Product, Store
from app.services.matching import find_cross_chain_matches


ALL_CHAINS = ["countdown", "new_world", "paknsave"]


def _effective_price(price_nzd: float, promo_price_nzd: float | None, promo_ends_at: datetime | None) -> float:
    """Return effective price, ignoring expired promos."""
    if promo_price_nzd is not None:
        if promo_ends_at is None or promo_ends_at > datetime.now(tz=timezone.utc):
            return promo_price_nzd
    return price_nzd


async def compare_trolley(
    session: AsyncSession,
    *,
    items: list[dict],
    lat: float,
    lon: float,
    radius_km: float,
) -> dict:
    """Compare trolley items across nearby stores.

    Args:
        items: list of {product_id: UUID, quantity: int}
        lat, lon: user location
        radius_km: search radius

    Returns:
        {stores: [...], items: [...], summary: {...}}
    """
    if not items:
        return {"stores": [], "items": [], "summary": {"total_items": 0}}

    # 1. Get nearby stores with distance
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
    store_result = await session.execute(store_query)
    nearby_stores = [(store, dist) for store, dist in store_result.all()]

    if not nearby_stores:
        return {"stores": [], "items": [], "summary": {"total_items": len(items)}}

    store_map: dict[UUID, tuple[Store, float]] = {}
    store_ids: list[UUID] = []
    for store, dist in nearby_stores:
        store_map[store.id] = (store, dist)
        store_ids.append(store.id)

    # 2. Load source products
    product_ids = [item["product_id"] for item in items]
    quantity_map = {item["product_id"]: item["quantity"] for item in items}

    product_query = select(Product).where(Product.id.in_(product_ids))
    product_result = await session.execute(product_query)
    source_products = {p.id: p for p in product_result.scalars().all()}

    # 3. Find cross-chain matches for each product
    # match_map: source_product_id -> {chain -> [candidate products]}
    match_map: dict[UUID, dict[str, list[dict]]] = {}
    # all_matched_product_ids includes source + matched product IDs
    all_product_ids: set[UUID] = set(product_ids)

    for pid, product in source_products.items():
        target_chains = [c for c in ALL_CHAINS if c != product.chain]
        matches = await find_cross_chain_matches(
            session,
            product_id=pid,
            source_chain=product.chain,
            product_name=product.name,
            product_brand=product.brand,
            product_size=product.size,
            target_chains=target_chains,
            store_ids=store_ids,
        )
        match_map[pid] = matches
        # Add best match per chain to the set
        for chain, candidates in matches.items():
            if candidates:
                all_product_ids.add(candidates[0]["product_id"])

    # 4. Batch-fetch all prices for source + matched products at nearby stores
    price_query = (
        select(Price)
        .where(
            and_(
                Price.product_id.in_(list(all_product_ids)),
                Price.store_id.in_(store_ids),
            )
        )
    )
    price_result = await session.execute(price_query)
    all_prices = price_result.scalars().all()

    # Index: (product_id, store_id) -> Price
    price_index: dict[tuple[UUID, UUID], Price] = {}
    for price in all_prices:
        price_index[(price.product_id, price.store_id)] = price

    # 5. Build source items info for response
    source_items = []
    for item in items:
        pid = item["product_id"]
        product = source_products.get(pid)
        if product:
            source_items.append({
                "product_id": str(pid),
                "name": product.name,
                "brand": product.brand,
                "size": product.size,
                "chain": product.chain,
                "image_url": product.image_url,
                "quantity": quantity_map[pid],
            })

    # 6. Build per-store breakdowns
    store_breakdowns = []
    for store_id, (store, distance) in store_map.items():
        store_items = []
        estimated_total = 0.0
        items_available = 0

        for item in items:
            pid = item["product_id"]
            qty = item["quantity"]
            product = source_products.get(pid)
            if not product:
                store_items.append({
                    "source_product_id": str(pid),
                    "source_product_name": "Unknown product",
                    "quantity": qty,
                    "available": False,
                    "matched_product_id": None,
                    "matched_product_name": None,
                    "price": None,
                    "line_total": None,
                })
                continue

            # Determine which product to look up at this store
            resolved_pid = pid
            resolved_name = product.name
            if store.chain != product.chain:
                # Look up cross-chain match
                chain_matches = match_map.get(pid, {}).get(store.chain, [])
                if chain_matches:
                    resolved_pid = chain_matches[0]["product_id"]
                    resolved_name = chain_matches[0]["name"]

            price = price_index.get((resolved_pid, store_id))
            if price:
                eff_price = _effective_price(price.price_nzd, price.promo_price_nzd, price.promo_ends_at)
                line_total = round(eff_price * qty, 2)
                estimated_total += line_total
                items_available += 1
                store_items.append({
                    "source_product_id": str(pid),
                    "source_product_name": product.name,
                    "quantity": qty,
                    "available": True,
                    "matched_product_id": str(resolved_pid),
                    "matched_product_name": resolved_name,
                    "price": eff_price,
                    "line_total": line_total,
                })
            else:
                store_items.append({
                    "source_product_id": str(pid),
                    "source_product_name": product.name,
                    "quantity": qty,
                    "available": False,
                    "matched_product_id": str(resolved_pid) if resolved_pid != pid else None,
                    "matched_product_name": resolved_name if resolved_pid != pid else None,
                    "price": None,
                    "line_total": None,
                })

        items_total = len(items)
        store_breakdowns.append({
            "store_id": str(store_id),
            "store_name": store.name,
            "chain": store.chain,
            "distance_km": round(distance / 1000, 2),
            "estimated_total": round(estimated_total, 2),
            "items_available": items_available,
            "items_total": items_total,
            "is_complete": items_available == items_total,
            "items": store_items,
        })

    # Sort: complete stores first, then by estimated total
    store_breakdowns.sort(key=lambda s: (not s["is_complete"], s["estimated_total"]))

    return {
        "stores": store_breakdowns,
        "items": source_items,
        "summary": {
            "total_items": len(items),
            "total_stores": len(store_breakdowns),
            "complete_stores": sum(1 for s in store_breakdowns if s["is_complete"]),
        },
    }


__all__ = ["compare_trolley"]
