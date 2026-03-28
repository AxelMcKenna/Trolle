from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography

from app.db.models import DeliverySlot, Price, Product, Store
from app.services.fulfillment import compute_fulfillment_fee, store_supports_method
from app.services.matching import find_cross_chain_matches


ALL_CHAINS = ["countdown", "new_world", "paknsave"]


def _effective_price(
    price_nzd: float,
    promo_price_nzd: float | None,
    promo_ends_at: datetime | None,
    is_member_only: bool = False,
    has_loyalty_card: bool = True,
) -> float:
    """Return effective price, ignoring expired promos and member-only promos without card."""
    if promo_price_nzd is not None:
        if is_member_only and not has_loyalty_card:
            return price_nzd
        if promo_ends_at is None or promo_ends_at > datetime.now(tz=timezone.utc):
            return promo_price_nzd
    return price_nzd


def _best_fulfillment_for_store(
    store: Store,
    subtotal: float,
) -> tuple[str, float]:
    """Pick the cheapest fulfillment method a store supports and return (method, fee).

    Priority: in_store (always free) > click_collect > delivery.
    """
    # In-store is always available and free
    best_method = "in_store"
    best_fee = 0.0

    if store.click_collect is True:
        cc_fee = compute_fulfillment_fee(
            chain=store.chain, subtotal=subtotal, method="click_collect",
            cc_fee_nzd=store.cc_fee_nzd,
        )
        if cc_fee <= best_fee:
            best_method = "click_collect"
            best_fee = cc_fee

    if store.delivery is True:
        del_fee = compute_fulfillment_fee(
            chain=store.chain, subtotal=subtotal, method="delivery",
            delivery_fee_nzd=store.delivery_fee_nzd,
            free_delivery_threshold_nzd=store.free_delivery_threshold_nzd,
        )
        if del_fee < best_fee:
            best_method = "delivery"
            best_fee = del_fee

    return best_method, best_fee


async def compare_trolley(
    session: AsyncSession,
    *,
    items: list[dict],
    lat: float,
    lon: float,
    radius_km: float,
    loyalty_cards: dict[str, bool] | None = None,
    fulfillment_method: str = "any",
) -> dict:
    """Compare trolley items across nearby stores.

    Args:
        items: list of {product_id: UUID, quantity: int}
        lat, lon: user location
        radius_km: search radius
        fulfillment_method: "in_store", "click_collect", "delivery", or "any"

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

    # Filter stores by fulfillment capability
    if fulfillment_method != "any":
        nearby_stores = [
            (store, dist) for store, dist in nearby_stores
            if store_supports_method(
                method=fulfillment_method,
                click_collect=store.click_collect,
                delivery=store.delivery,
            )
        ]

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

    async def _match_one(pid: UUID, product: Any) -> tuple[UUID, dict[str, list[dict]]]:
        target_chains = [c for c in ALL_CHAINS if c != product.chain]
        matches = await find_cross_chain_matches(
            session,
            product_id=pid,
            source_chain=product.chain,
            product_name=product.name,
            product_brand=product.brand,
            product_size=product.size,
            product_department=product.department,
            product_subcategory=product.subcategory,
            source_embedding=getattr(product, "embedding", None),
            target_chains=target_chains,
            store_ids=store_ids,
            product_volume_ml=getattr(product, "volume_ml", None),
            product_weight_g=getattr(product, "weight_g", None),
            product_pack_count=getattr(product, "pack_count", None),
        )
        return pid, matches

    match_results = await asyncio.gather(
        *[_match_one(pid, product) for pid, product in source_products.items()]
    )
    for pid, matches in match_results:
        match_map[pid] = matches
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
                "department": product.department,
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
                has_card = loyalty_cards.get(store.chain, True) if loyalty_cards else True
                eff_price = _effective_price(
                    price.price_nzd, price.promo_price_nzd, price.promo_ends_at,
                    is_member_only=price.is_member_only, has_loyalty_card=has_card,
                )
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
                    "is_member_only": price.is_member_only,
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

        estimated_total = round(estimated_total, 2)
        items_total = len(items)

        # Compute fulfillment fee
        if fulfillment_method == "any":
            chosen_method, delivery_fee = _best_fulfillment_for_store(store, estimated_total)
        else:
            chosen_method = fulfillment_method
            delivery_fee = compute_fulfillment_fee(
                chain=store.chain,
                subtotal=estimated_total,
                method=fulfillment_method,
                delivery_fee_nzd=store.delivery_fee_nzd,
                free_delivery_threshold_nzd=store.free_delivery_threshold_nzd,
                cc_fee_nzd=store.cc_fee_nzd,
            )

        delivery_fee = round(delivery_fee, 2)
        estimated_total_with_fee = round(estimated_total + delivery_fee, 2)

        # Check minimum order requirement
        meets_minimum = True
        if store.min_order_nzd and chosen_method in ("delivery", "click_collect"):
            meets_minimum = estimated_total >= store.min_order_nzd

        store_breakdowns.append({
            "store_id": str(store_id),
            "store_name": store.name,
            "chain": store.chain,
            "distance_km": round(distance / 1000, 2),
            "estimated_total": estimated_total,
            "items_available": items_available,
            "items_total": items_total,
            "is_complete": items_available == items_total,
            "items": store_items,
            # Fulfillment fields
            "fulfillment_method": chosen_method,
            "delivery_fee": delivery_fee,
            "estimated_total_with_fee": estimated_total_with_fee,
            "click_collect": store.click_collect,
            "delivery": store.delivery,
            "meets_minimum_order": meets_minimum,
        })

    # Batch-query slot availability for all nearby stores
    now = datetime.now(tz=timezone.utc)
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
    slot_index: dict[tuple, datetime] = {}
    for row in slot_result.all():
        slot_index[(str(row.store_id), row.fulfillment_type)] = row.next_slot

    # Attach slot availability to each store breakdown
    for sb in store_breakdowns:
        sid = sb["store_id"]
        next_del = slot_index.get((sid, "delivery"))
        next_cc = slot_index.get((sid, "click_collect"))
        sb["delivery_available"] = next_del is not None if sb["delivery"] is not False else False
        sb["cc_available"] = next_cc is not None if sb["click_collect"] is not False else False
        sb["next_delivery_slot"] = next_del.isoformat() if next_del else None
        sb["next_cc_slot"] = next_cc.isoformat() if next_cc else None

    # Sort: complete stores first, then by total including fee
    store_breakdowns.sort(key=lambda s: (not s["is_complete"], s["estimated_total_with_fee"]))

    return {
        "stores": store_breakdowns,
        "items": source_items,
        "summary": {
            "total_items": len(items),
            "total_stores": len(store_breakdowns),
            "complete_stores": sum(1 for s in store_breakdowns if s["is_complete"]),
        },
    }


async def split_compare_trolley(
    session: AsyncSession,
    *,
    items: list[dict],
    lat: float,
    lon: float,
    radius_km: float,
    max_stores: int = 2,
    loyalty_cards: dict[str, bool] | None = None,
    fulfillment_method: str = "any",
) -> dict:
    """Optimize a trolley split across up to max_stores stores.

    Reuses compare_trolley to get per-store breakdowns, then finds the
    optimal assignment of items to a subset of stores.
    """
    from itertools import combinations

    # Get full comparison first
    comparison = await compare_trolley(
        session,
        items=items,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        loyalty_cards=loyalty_cards,
        fulfillment_method=fulfillment_method,
    )

    store_breakdowns = comparison["stores"]
    if not store_breakdowns:
        return {
            "single_best": None,
            "single_best_total": 0,
            "splits": [],
            "savings_vs_single": 0,
        }

    single_best = store_breakdowns[0]
    single_best_total = single_best["estimated_total_with_fee"]

    # Build price matrix: store_idx -> {source_product_id -> (price, item_data)}
    item_ids = [item["product_id"] for item in items]
    quantity_map = {item["product_id"]: item["quantity"] for item in items}

    store_prices: list[dict] = []  # list of {source_pid: effective_price_or_None}
    for sb in store_breakdowns:
        prices = {}
        for si in sb["items"]:
            if si["available"] and si["price"] is not None:
                prices[si["source_product_id"]] = si
        store_prices.append(prices)

    # Prune to top N stores by item availability for combinatorics
    top_n = min(10, len(store_breakdowns))
    candidate_indices = list(range(top_n))

    best_splits: list[dict] = []

    for n_stores in range(2, max_stores + 1):
        best_total = float("inf")
        best_assignment: dict | None = None

        for combo in combinations(candidate_indices, n_stores):
            total = 0.0
            all_covered = True
            assignments: dict[int, list] = {idx: [] for idx in combo}

            for item_id in item_ids:
                pid = str(item_id) if not isinstance(item_id, str) else item_id
                qty = quantity_map[item_id]

                # Find cheapest store in this combo that has the item
                best_store_idx = None
                best_price = float("inf")

                for idx in combo:
                    item_data = store_prices[idx].get(pid)
                    if item_data and item_data["price"] is not None:
                        if item_data["price"] < best_price:
                            best_price = item_data["price"]
                            best_store_idx = idx

                if best_store_idx is not None:
                    total += round(best_price * qty, 2)
                    assignments[best_store_idx].append(store_prices[best_store_idx][pid])
                else:
                    all_covered = False

            # Add delivery fees for each store in the combo
            combo_fees = 0.0
            for idx in combo:
                if assignments[idx]:  # only charge fee if store has items
                    combo_fees += store_breakdowns[idx].get("delivery_fee", 0.0)
            total_with_fees = round(total + combo_fees, 2)

            if total_with_fees < best_total:
                best_total = total_with_fees
                best_assignment = {
                    "assignments": [
                        {
                            "store_id": store_breakdowns[idx]["store_id"],
                            "store_name": store_breakdowns[idx]["store_name"],
                            "chain": store_breakdowns[idx]["chain"],
                            "distance_km": store_breakdowns[idx]["distance_km"],
                            "items": assigned_items,
                            "subtotal": round(
                                sum(
                                    (i["price"] or 0) * i["quantity"]
                                    for i in assigned_items
                                ),
                                2,
                            ),
                            "delivery_fee": store_breakdowns[idx].get("delivery_fee", 0.0),
                            "subtotal_with_fee": round(
                                sum(
                                    (i["price"] or 0) * i["quantity"]
                                    for i in assigned_items
                                ) + store_breakdowns[idx].get("delivery_fee", 0.0),
                                2,
                            ),
                        }
                        for idx, assigned_items in assignments.items()
                        if assigned_items  # skip empty stores
                    ],
                    "grand_total": round(best_total, 2),
                    "store_count": n_stores,
                }

        if best_assignment:
            best_splits.append(best_assignment)

    savings = round(single_best_total - (best_splits[-1]["grand_total"] if best_splits else single_best_total), 2)

    return {
        "single_best": single_best,
        "single_best_total": single_best_total,
        "splits": best_splits,
        "savings_vs_single": max(0, savings),
    }


__all__ = ["compare_trolley", "split_compare_trolley"]
