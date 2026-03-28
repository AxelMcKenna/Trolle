from __future__ import annotations

from typing import Any
from uuid import UUID

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography

from app.core.config import get_settings
from app.db.models import Price, Product, Store
from app.schemas.products import PriceSchema, ProductDetailSchema, ProductListResponse, ProductSchema, StoreListResponse, StoreSchema
from app.schemas.queries import ProductQueryParams
from app.services.cache import cached_json
from app.services.parser_utils import CATEGORY_HIERARCHY, format_product_name
from app.services.pricing import compute_pricing_metrics

settings = get_settings()

# Prices not seen in over 7 days are considered stale
_STALE_THRESHOLD = timedelta(days=7)


def _effective_price(price: Price) -> float:
    """Return the effective price, ignoring expired promos."""
    if price.promo_price_nzd is not None:
        if price.promo_ends_at is None or price.promo_ends_at > datetime.now(tz=timezone.utc):
            return price.promo_price_nzd
    return price.price_nzd


def _is_stale(price: Price) -> bool:
    """Return True if the price hasn't been seen recently."""
    if price.last_seen_at is None:
        return True
    cutoff = datetime.now(tz=timezone.utc)
    # last_seen_at may be naive (utcnow) — treat as UTC
    last_seen = price.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (cutoff - last_seen) > _STALE_THRESHOLD


def _store_bucket_key(lat: float, lon: float, radius_km: float) -> str:
    return f"stores_nearby:{round(lat, 2)}:{round(lon, 2)}:{round(radius_km, 1)}"


async def _get_store_ids_within_radius(
    session: AsyncSession,
    *,
    lat: float,
    lon: float,
    radius_km: float,
) -> list[UUID]:
    cache_key = _store_bucket_key(lat, lon, radius_km)

    async def producer() -> list[str]:
        user_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        user_point_geog = cast(user_point, Geography)
        radius_m = radius_km * 1000
        query = (
            select(Store.id)
            .where(Store.geog.is_not(None))
            .where(func.ST_DWithin(Store.geog, user_point_geog, radius_m))
        )
        result = await session.execute(query)
        return [str(store_id) for store_id in result.scalars().all()]

    cached_ids = await cached_json(cache_key, settings.cache_ttl_stores_nearby, producer)
    return [UUID(store_id) for store_id in cached_ids]


def _build_sort_order(
    *,
    sort: str,
    discount_ratio: Any,
    unit_price_sort: Any,
    effective_price: Any,
    distance_m: Any | None,
    relevance: Any | None = None,
) -> list[Any]:
    tie_breakers = [Price.price_last_changed_at.desc(), Product.name.asc(), Price.id.asc()]
    # When a search query is active, prepend relevance as primary/tiebreaker
    relevance_prefix = [relevance.desc().nulls_last()] if relevance is not None else []
    if sort == "discount":
        return [discount_ratio.desc().nulls_last(), *relevance_prefix, *tie_breakers]
    if sort == "unit_price":
        return [unit_price_sort.asc().nulls_last(), *relevance_prefix, *tie_breakers]
    if sort == "total_price":
        return [*relevance_prefix, effective_price.asc().nulls_last(), *tie_breakers]
    if sort == "newest":
        return [Price.price_last_changed_at.desc(), *relevance_prefix, Product.name.asc(), Price.id.asc()]
    if sort == "distance" and distance_m is not None:
        return [distance_m.asc().nulls_last(), *relevance_prefix, *tie_breakers]
    # Default: relevance first (if searching), then effective price
    return [*relevance_prefix, effective_price.asc().nulls_last(), *tie_breakers]


async def fetch_products(
    session: AsyncSession,
    params: ProductQueryParams,
) -> ProductListResponse:
    page = max(params.page, 1)
    page_size = max(min(params.page_size, 100), 1)

    filters = []
    user_point_geog = None
    if params.lat is not None and params.lon is not None and params.radius_km is not None:
        nearby_store_ids = await _get_store_ids_within_radius(
            session,
            lat=params.lat,
            lon=params.lon,
            radius_km=params.radius_km,
        )
        if not nearby_store_ids:
            return ProductListResponse(items=[], total=0, page=page, page_size=page_size)

        user_point = func.ST_SetSRID(func.ST_MakePoint(params.lon, params.lat), 4326)
        user_point_geog = cast(user_point, Geography)
        filters.append(Store.id.in_(nearby_store_ids))

    relevance = None
    if params.q:
        pattern = f"%{params.q.lower()}%"
        filters.append(
            or_(
                func.lower(Product.name).like(pattern),
                func.lower(Product.brand).like(pattern),
            )
        )
        # Category-aware relevance scoring: boost products whose department or
        # subcategory matches the query term, so "chicken" in Meat & Seafood
        # ranks above "chicken" in Chips & Snacks.
        q_lower = params.q.lower()
        q_pattern = f"%{q_lower}%"
        category_relevance = case(
            (func.lower(func.coalesce(Product.subcategory, "")).like(q_pattern), 0.4),
            (func.lower(func.coalesce(Product.department, "")).like(q_pattern), 0.3),
            else_=0.0,
        )

        # Hybrid: blend vector similarity with category relevance when embeddings available
        vector_sim = None
        if settings.embedding_enabled:
            from app.services.embeddings import embed_texts

            query_embedding = embed_texts([params.q])
            if query_embedding and Product.__table__.columns.get("embedding") is not None:
                from app.db.models import Product as ProductModel

                # cosine_distance returns distance (0=identical), convert to similarity
                vector_sim = (1 - ProductModel.embedding.cosine_distance(query_embedding[0]))

        if vector_sim is not None:
            relevance = (vector_sim * 0.7 + category_relevance * 0.3).label("relevance")
        else:
            relevance = category_relevance.label("relevance")
    if params.chain:
        filters.append(Product.chain.in_(params.chain))
    if params.store:
        filters.append(Store.id.in_([UUID(store_id) for store_id in params.store]))
    if params.category:
        # Expand categories to include subcategories
        expanded_categories = set(params.category)
        for requested_cat in params.category:
            for subcat, parent in CATEGORY_HIERARCHY.items():
                if parent == requested_cat:
                    expanded_categories.add(subcat)
        filters.append(
            or_(
                Product.category.in_(list(expanded_categories)),
                Product.department.in_(list(expanded_categories)),
                Product.subcategory.in_(list(expanded_categories)),
            )
        )
    # Only count a promo as valid if promo_ends_at is NULL or in the future
    now_ts = func.now()
    promo_conditions = [
        Price.promo_price_nzd.is_not(None),
        or_(Price.promo_ends_at.is_(None), Price.promo_ends_at > now_ts),
    ]
    # When member_prices=False, exclude member-only promos from effective price
    if not params.member_prices:
        promo_conditions.append(Price.is_member_only == False)  # noqa: E712
    valid_promo = case(
        (
            and_(*promo_conditions),
            Price.promo_price_nzd,
        ),
        else_=None,
    )
    effective_price = func.coalesce(valid_promo, Price.price_nzd)
    if params.price_min is not None:
        filters.append(effective_price >= params.price_min)
    if params.price_max is not None:
        filters.append(effective_price <= params.price_max)
    if params.promo_only:
        # Only return products with actual, non-expired discounts
        filters.append(Price.promo_price_nzd.is_not(None))
        filters.append(Price.promo_price_nzd < Price.price_nzd)
        filters.append(or_(Price.promo_ends_at.is_(None), Price.promo_ends_at > now_ts))

    discount_ratio = (
        (Price.price_nzd - effective_price)
        / func.nullif(Price.price_nzd, 0)
    ).label("discount_ratio")
    unit_price_sort = Product.unit_price.label("unit_price_sort")
    distance_m = (
        func.ST_Distance(Store.geog, user_point_geog).label("distance_m")
        if user_point_geog is not None
        else None
    )
    distance_m_or_null = distance_m if distance_m is not None else literal(None).label("distance_m")

    sort_order = _build_sort_order(
        sort=params.sort,
        discount_ratio=discount_ratio,
        unit_price_sort=unit_price_sort,
        effective_price=effective_price,
        distance_m=distance_m,
        relevance=relevance,
    )

    if params.unique_products:
        name_key = func.lower(func.trim(Product.name)).label("name_key")
        inner = (
            select(
                Product.id.label("product_id"),
                Price.id.label("price_id"),
                Store.id.label("store_id"),
                discount_ratio,
                distance_m_or_null,
                func.row_number()
                .over(
                    partition_by=(name_key, Product.size),
                    order_by=tuple(sort_order),
                )
                .label("rn"),
            )
            .select_from(Product)
            .join(Price, Price.product_id == Product.id)
            .join(Store, Store.id == Price.store_id)
        )
        if filters:
            inner = inner.where(and_(*filters))

        inner_subq = inner.subquery()
        query = (
            select(Product, Price, Store, inner_subq.c.discount_ratio, inner_subq.c.distance_m)
            .select_from(inner_subq)
            .join(Product, Product.id == inner_subq.c.product_id)
            .join(Price, Price.id == inner_subq.c.price_id)
            .join(Store, Store.id == inner_subq.c.store_id)
            .where(inner_subq.c.rn == 1)
        )
        query = query.order_by(*sort_order)

        total_result = await session.execute(
            select(func.count()).select_from(inner_subq).where(inner_subq.c.rn == 1)
        )
        total = total_result.scalar_one()
    else:
        query = (
            select(Product, Price, Store, distance_m_or_null)
            .join(Price, Price.product_id == Product.id)
            .join(Store, Store.id == Price.store_id)
        )
        count_query = (
            select(func.count(Price.id))
            .select_from(Product)
            .join(Price, Price.product_id == Product.id)
            .join(Store, Store.id == Price.store_id)
        )
        if filters:
            where_clause = and_(*filters)
            query = query.where(where_clause)
            count_query = count_query.where(where_clause)

        query = query.order_by(*sort_order)
        total_result = await session.execute(count_query)
        total = total_result.scalar_one()

    query = query.limit(page_size).offset((page - 1) * page_size)

    result = await session.execute(query)
    rows = result.all()
    items: list[ProductSchema] = []

    for row in rows:
        if params.unique_products:
            product, price, store, _, distance_m_value = row
        else:
            product, price, store, distance_m_value = row
        metrics = compute_pricing_metrics(
            unit_price=product.unit_price,
            unit_measure=product.unit_measure,
        )
        distance = round(distance_m_value / 1000, 2) if distance_m_value is not None else None
        items.append(
            ProductSchema(
                id=product.id,
                name=format_product_name(product.name, product.brand),
                brand=product.brand,
                category=product.category,
                chain=product.chain,
                size=product.size,
                department=product.department,
                subcategory=product.subcategory,
                image_url=product.image_url,
                product_url=product.product_url,
                price=PriceSchema(
                    store_id=store.id,
                    store_name=store.name,
                    chain=store.chain,
                    price_nzd=price.price_nzd,
                    promo_price_nzd=price.promo_price_nzd,
                    promo_text=price.promo_text,
                    promo_ends_at=price.promo_ends_at,
                    unit_price=metrics.unit_price,
                    unit_measure=metrics.unit_measure,
                    is_member_only=price.is_member_only,
                    is_stale=_is_stale(price),
                    distance_km=distance,
                ),
                last_updated=price.last_seen_at,
            )
        )

    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


async def fetch_product_detail(
    session: AsyncSession,
    product_id: UUID,
    *,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
) -> ProductDetailSchema:
    has_location = lat is not None and lon is not None and radius_km is not None

    # Build optional distance column
    user_point_geog = None
    distance_col = literal(None).label("distance_m")
    if has_location:
        user_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        user_point_geog = cast(user_point, Geography)
        distance_col = func.ST_Distance(Store.geog, user_point_geog).label("distance_m")

    query = (
        select(Product, Price, Store, distance_col)
        .join(Price, Price.product_id == Product.id)
        .join(Store, Store.id == Price.store_id)
        .where(Product.id == product_id)
    )

    # If location provided, optionally filter to nearby stores
    if has_location:
        nearby_ids = await _get_store_ids_within_radius(
            session, lat=lat, lon=lon, radius_km=radius_km,
        )
        if nearby_ids:
            query = query.where(Store.id.in_(nearby_ids))

    # Sort by effective price (cheapest first)
    query = query.order_by(func.coalesce(Price.promo_price_nzd, Price.price_nzd).asc())

    result = await session.execute(query)
    rows = result.all()
    if not rows:
        raise ValueError("Product not found")

    product = rows[0][0]
    metrics = compute_pricing_metrics(
        unit_price=product.unit_price,
        unit_measure=product.unit_measure,
    )

    prices: list[PriceSchema] = []
    latest_seen = rows[0][1].last_seen_at
    for _, price, store, dist_m in rows:
        distance = round(dist_m / 1000, 2) if dist_m is not None else None
        prices.append(PriceSchema(
            store_id=store.id,
            store_name=store.name,
            chain=store.chain,
            price_nzd=price.price_nzd,
            promo_price_nzd=price.promo_price_nzd,
            promo_text=price.promo_text,
            promo_ends_at=price.promo_ends_at,
            unit_price=metrics.unit_price,
            unit_measure=metrics.unit_measure,
            is_member_only=price.is_member_only,
            is_stale=_is_stale(price),
            distance_km=distance,
        ))
        if price.last_seen_at and price.last_seen_at > latest_seen:
            latest_seen = price.last_seen_at

    return ProductDetailSchema(
        id=product.id,
        name=format_product_name(product.name, product.brand),
        brand=product.brand,
        category=product.category,
        chain=product.chain,
        size=product.size,
        department=product.department,
        subcategory=product.subcategory,
        image_url=product.image_url,
        product_url=product.product_url,
        prices=prices,
        last_updated=latest_seen,
    )


async def fetch_stores_nearby(
    session: AsyncSession,
    *,
    lat: float,
    lon: float,
    radius_km: float,
) -> StoreListResponse:
    user_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    user_point_geog = cast(user_point, Geography)

    store_ids = await _get_store_ids_within_radius(session, lat=lat, lon=lon, radius_km=radius_km)
    if not store_ids:
        return StoreListResponse(items=[])

    distance_m = func.ST_Distance(Store.geog, user_point_geog).label("distance_m")
    query = (
        select(Store, distance_m)
        .where(Store.id.in_(store_ids))
        .order_by(distance_m)
    )
    result = await session.execute(query)
    items = [
        StoreSchema(
            id=store.id,
            name=store.name,
            chain=store.chain,
            lat=store.lat,
            lon=store.lon,
            address=store.address,
            region=store.region,
            distance_km=round(distance / 1000, 2),
            click_collect=store.click_collect,
            delivery=store.delivery,
            delivery_fee_nzd=store.delivery_fee_nzd,
            cc_fee_nzd=store.cc_fee_nzd,
            min_order_nzd=store.min_order_nzd,
            free_delivery_threshold_nzd=store.free_delivery_threshold_nzd,
        )
        for store, distance in result.all()
    ]
    return StoreListResponse(items=items)


__all__ = ["fetch_products", "fetch_product_detail", "fetch_stores_nearby"]
