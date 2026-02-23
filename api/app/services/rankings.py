from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from geoalchemy2 import Geography

from app.db.models import Price, Product, Store
from app.schemas.rankings import RankedStore, StoreRankingResponse
from app.services.cache import cached_json
from app.services.parser_utils import CATEGORY_HIERARCHY
from app.services.search import _get_store_ids_within_radius

from app.core.config import get_settings

settings = get_settings()

# Valid top-level categories (parents in the hierarchy)
VALID_CATEGORIES = sorted(set(CATEGORY_HIERARCHY.values()))

_SIMILARITY_THRESHOLD = 0.25


class UnionFind:
    """Disjoint-set data structure for merging transitive product matches."""

    def __init__(self) -> None:
        self._parent: dict[Any, Any] = {}

    def find(self, x: Any) -> Any:
        if x not in self._parent:
            self._parent[x] = x
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: Any, b: Any) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra

    def groups(self) -> dict[Any, list[Any]]:
        result: dict[Any, list[Any]] = defaultdict(list)
        for x in self._parent:
            result[self.find(x)].append(x)
        return result


def _expand_category(category: str) -> list[str]:
    """Expand a top-level category to include its subcategories."""
    expanded = {category}
    for subcat, parent in CATEGORY_HIERARCHY.items():
        if parent == category:
            expanded.add(subcat)
    return list(expanded)


def _compute_rankings(
    store_info: dict[UUID, dict],
    groups: list[list[tuple[UUID, float]]],
) -> list[RankedStore]:
    """Compute price index for each store from comparison groups.

    Each group is a list of (store_id, effective_price) pairs representing
    the same product across stores. The price index is:
        mean(store_price / min_price_in_group) * 100

    So 100 = cheapest on average, higher = more expensive.
    """
    # Per-store accumulators
    ratios: dict[UUID, list[float]] = defaultdict(list)
    cheapest_counts: dict[UUID, int] = defaultdict(int)
    store_prices: dict[UUID, list[float]] = defaultdict(list)
    matched_stores: dict[UUID, set] = defaultdict(set)

    for group_idx, group in enumerate(groups):
        if len(group) < 2:
            continue
        # Aggregate: pick cheapest price per store in this group
        store_best: dict[UUID, float] = {}
        for store_id, price in group:
            if store_id not in store_best or price < store_best[store_id]:
                store_best[store_id] = price

        if len(store_best) < 2:
            continue

        min_price = min(store_best.values())
        if min_price <= 0:
            continue

        for store_id, price in store_best.items():
            ratio = price / min_price
            ratios[store_id].append(ratio)
            store_prices[store_id].append(price)
            matched_stores[store_id].add(group_idx)
            if price == min_price:
                cheapest_counts[store_id] += 1

    ranked: list[RankedStore] = []
    for store_id, info in store_info.items():
        store_ratios = ratios.get(store_id, [])
        if not store_ratios:
            price_index = 0.0
            avg_price = 0.0
        else:
            price_index = round((sum(store_ratios) / len(store_ratios)) * 100, 1)
            prices = store_prices[store_id]
            avg_price = round(sum(prices) / len(prices), 2)

        ranked.append(
            RankedStore(
                store_id=store_id,
                store_name=info["name"],
                chain=info["chain"],
                distance_km=info["distance_km"],
                price_index=price_index,
                matched_products=len(matched_stores.get(store_id, set())),
                total_category_products=info.get("total_products", 0),
                avg_effective_price=avg_price,
                cheapest_count=cheapest_counts.get(store_id, 0),
            )
        )

    # Sort: stores with matches first (by price_index), then unmatched stores
    ranked.sort(key=lambda s: (s.matched_products == 0, s.price_index))
    return ranked


async def rank_stores_by_category(
    session: AsyncSession,
    category: str,
    lat: float,
    lon: float,
    radius_km: float,
) -> StoreRankingResponse:
    cache_key = f"store_rankings:{category}:{round(lat, 2)}:{round(lon, 2)}:{round(radius_km, 1)}"

    async def _produce() -> dict:
        return (await _rank_stores_uncached(session, category, lat, lon, radius_km)).model_dump(mode="json")

    data = await cached_json(cache_key, settings.api_cache_ttl_seconds, _produce)
    return StoreRankingResponse(**data)


async def _rank_stores_uncached(
    session: AsyncSession,
    category: str,
    lat: float,
    lon: float,
    radius_km: float,
) -> StoreRankingResponse:
    # 1. Get nearby store IDs
    store_ids = await _get_store_ids_within_radius(session, lat=lat, lon=lon, radius_km=radius_km)
    if not store_ids:
        return StoreRankingResponse(category=category, stores=[], total_comparison_products=0)

    # 2. Fetch stores with distances
    user_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    user_point_geog = cast(user_point, Geography)
    distance_m = func.ST_Distance(Store.geog, user_point_geog).label("distance_m")

    store_query = select(Store, distance_m).where(Store.id.in_(store_ids)).order_by(distance_m)
    store_result = await session.execute(store_query)

    store_info: dict[UUID, dict] = {}
    for store, dist in store_result.all():
        store_info[store.id] = {
            "name": store.name,
            "chain": store.chain,
            "distance_km": round(dist / 1000, 2),
        }

    # 3. Batch query: all products in category with prices at nearby stores
    expanded_cats = _expand_category(category)

    now_ts = func.now()
    valid_promo = case(
        (
            and_(
                Price.promo_price_nzd.is_not(None),
                or_(Price.promo_ends_at.is_(None), Price.promo_ends_at > now_ts),
            ),
            Price.promo_price_nzd,
        ),
        else_=None,
    )
    effective_price = func.coalesce(valid_promo, Price.price_nzd).label("effective_price")

    cat_filter = or_(
        Product.category.in_(expanded_cats),
        Product.department.in_(expanded_cats),
        Product.subcategory.in_(expanded_cats),
    )

    products_query = (
        select(
            Product.id,
            Product.chain,
            Product.source_product_id,
            Product.name,
            Product.brand,
            Product.size,
            Product.department,
            Price.store_id,
            effective_price,
        )
        .join(Price, Price.product_id == Product.id)
        .where(and_(Price.store_id.in_(store_ids), cat_filter))
    )

    result = await session.execute(products_query)
    rows = result.all()

    if not rows:
        return StoreRankingResponse(category=category, stores=list(_compute_rankings(store_info, [])), total_comparison_products=0)

    # Count total products per store for context
    store_product_counts: dict[UUID, int] = defaultdict(int)
    for row in rows:
        store_product_counts[row.store_id] += 1
    for sid in store_info:
        store_info[sid]["total_products"] = store_product_counts.get(sid, 0)

    # 4. Build comparison groups
    # 4a. Same-chain: group by (chain, source_product_id)
    same_chain_groups: dict[tuple[str, str], list[tuple[UUID, float]]] = defaultdict(list)
    # Track representative product per source_product_id for cross-chain matching
    representatives: dict[tuple[str, str], dict] = {}

    for row in rows:
        product_id, chain, source_pid, name, brand, size, department, store_id, eff_price = row
        key = (chain, source_pid)
        same_chain_groups[key].append((store_id, float(eff_price)))
        if key not in representatives:
            representatives[key] = {
                "product_id": product_id,
                "chain": chain,
                "source_product_id": source_pid,
                "name": name,
                "brand": brand,
                "size": size,
                "department": department,
            }

    # 4b. Cross-chain: batch pg_trgm self-join on representative products
    uf = UnionFind()
    # Initialize all same-chain groups
    for key in same_chain_groups:
        uf.find(key)

    # Build cross-chain matches via a self-join on the product table
    rep_product_ids = [r["product_id"] for r in representatives.values()]

    if len(set(r["chain"] for r in representatives.values())) > 1:
        # Self-join: find similar products across chains using pg_trgm
        p1 = aliased(Product, name="p1")
        p2 = aliased(Product, name="p2")

        # Brand-stripped name expressions for both sides
        p1_clean = case(
            (
                and_(
                    p1.brand.is_not(None),
                    p1.brand != "",
                    func.strpos(func.lower(p1.name), func.lower(p1.brand)) == 1,
                ),
                func.ltrim(
                    func.substr(func.lower(p1.name), func.char_length(p1.brand) + 1),
                    " -\u2013",
                ),
            ),
            else_=func.lower(p1.name),
        )
        p2_clean = case(
            (
                and_(
                    p2.brand.is_not(None),
                    p2.brand != "",
                    func.strpos(func.lower(p2.name), func.lower(p2.brand)) == 1,
                ),
                func.ltrim(
                    func.substr(func.lower(p2.name), func.char_length(p2.brand) + 1),
                    " -\u2013",
                ),
            ),
            else_=func.lower(p2.name),
        )

        sim = func.similarity(p1_clean, p2_clean).label("sim")

        cross_query = (
            select(
                p1.chain.label("chain1"),
                p1.source_product_id.label("spid1"),
                p2.chain.label("chain2"),
                p2.source_product_id.label("spid2"),
                sim,
            )
            .where(
                and_(
                    p1.id.in_(rep_product_ids),
                    p2.id.in_(rep_product_ids),
                    p1.chain != p2.chain,
                    p1.department == p2.department,
                    func.coalesce(func.lower(p1.size), "") == func.coalesce(func.lower(p2.size), ""),
                    sim >= _SIMILARITY_THRESHOLD,
                )
            )
        )

        cross_result = await session.execute(cross_query)
        for chain1, spid1, chain2, spid2, _sim in cross_result.all():
            uf.union((chain1, spid1), (chain2, spid2))

    # Merge same-chain groups via UnionFind
    merged_groups_map = uf.groups()
    groups: list[list[tuple[UUID, float]]] = []
    for _root, members in merged_groups_map.items():
        group: list[tuple[UUID, float]] = []
        for key in members:
            group.extend(same_chain_groups.get(key, []))
        groups.append(group)

    # 5. Compute rankings
    ranked = _compute_rankings(store_info, groups)
    total_comparison = sum(1 for g in groups if len({sid for sid, _ in g}) >= 2)

    return StoreRankingResponse(
        category=category,
        stores=ranked,
        total_comparison_products=total_comparison,
    )


__all__ = ["rank_stores_by_category", "UnionFind", "VALID_CATEGORIES", "_compute_rankings"]
