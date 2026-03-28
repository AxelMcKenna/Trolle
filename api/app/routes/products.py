from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from geoalchemy2 import Geography
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import and_, cast, func, or_, select

from app.core.config import get_settings
from app.db.models import Price, PriceHistory, Product, Store
from app.db.session import get_async_session
from app.middleware import get_limiter
from app.schemas.products import (
    PriceHistoryResponse,
    ProductDetailSchema,
    ProductListResponse,
)
from app.schemas.queries import ProductQueryParams
from app.services.cache import cached_json
from app.services.search import fetch_product_detail, fetch_products

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])
settings = get_settings()


def _split_csv_params(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for value in values:
        for part in value.split(","):
            candidate = part.strip()
            if candidate:
                items.append(candidate)
    return items


async def _params(
    q: Optional[str] = Query(None),
    chain: Optional[list[str]] = Query(None),
    store: Optional[list[str]] = Query(None),
    category: Optional[list[str]] = Query(None),
    price_min: Optional[float] = Query(None),
    price_max: Optional[float] = Query(None),
    promo_only: bool = Query(False),
    member_prices: bool = Query(True),
    unique_products: bool = Query(False),
    sort: str = Query("total_price"),
    page: int = Query(1),
    page_size: int = Query(20),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius_km: Optional[float] = Query(None),
) -> ProductQueryParams:
    try:
        return ProductQueryParams(
            q=q,
            chain=_split_csv_params(chain),
            store=_split_csv_params(store),
            category=_split_csv_params(category),
            price_min=price_min,
            price_max=price_max,
            promo_only=promo_only,
            member_prices=member_prices,
            unique_products=unique_products,
            sort=sort,
            page=page,
            page_size=page_size,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_context=False),
        ) from exc


@router.get("", response_model=ProductListResponse)
async def list_products(params: ProductQueryParams = Depends(_params)) -> ProductListResponse:
    has_location = params.lat is not None and params.lon is not None and params.radius_km is not None

    # Validate location if provided
    if has_location:
        if not (-47 <= params.lat <= -34 and 165 <= params.lon <= 179):
            raise HTTPException(
                status_code=400,
                detail="Location must be within New Zealand"
            )
        if params.radius_km > 10:
            raise HTTPException(
                status_code=400,
                detail="Search radius cannot exceed 10km"
            )

    async with get_async_session() as session:
        cache_key = json.dumps(params.dict(), sort_keys=True)

        async def producer() -> dict:
            response = await fetch_products(session, params)
            return json.loads(response.json())

        ttl = settings.cache_ttl_product_list
        payload = await cached_json(cache_key, ttl, producer)
        return ProductListResponse.parse_obj(payload)


@router.get("/random-deal")
async def random_deal(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius_km: Optional[float] = Query(None, ge=1, le=10),
) -> dict:
    async with get_async_session() as session:
        now = datetime.now(timezone.utc)

        # Base filter: active promos only
        promo_filter = and_(
            Price.promo_price_nzd.isnot(None),
            Price.promo_price_nzd < Price.price_nzd,
            or_(Price.promo_ends_at.is_(None), Price.promo_ends_at > now),
        )

        query = (
            select(Product, Price, Store.name.label("store_name"), Store.chain.label("store_chain"))
            .join(Price, Price.product_id == Product.id)
            .join(Store, Price.store_id == Store.id)
            .where(promo_filter)
        )

        # Location filter
        if lat is not None and lon is not None and radius_km is not None:
            point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
            query = query.where(
                func.ST_DWithin(
                    Store.geog,
                    cast(point, Geography),
                    radius_km * 1000,
                )
            )

        # Count matching rows, pick random offset
        count_query = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_query)).scalar() or 0

        if total == 0:
            raise HTTPException(status_code=404, detail="No deals found")

        offset = random.randint(0, total - 1)
        row = (await session.execute(query.offset(offset).limit(1))).one()

        product = row[0]
        price = row[1]

        discount_pct = round((1 - price.promo_price_nzd / price.price_nzd) * 100)

        return {
            "id": str(product.id),
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "chain": product.chain,
            "size": product.size,
            "department": product.department,
            "subcategory": product.subcategory,
            "image_url": product.image_url,
            "product_url": product.product_url,
            "price": {
                "store_id": str(price.store_id),
                "store_name": row.store_name,
                "chain": row.store_chain,
                "price_nzd": price.price_nzd,
                "promo_price_nzd": price.promo_price_nzd,
                "promo_text": price.promo_text,
                "promo_ends_at": price.promo_ends_at.isoformat() if price.promo_ends_at else None,
                "is_member_only": price.is_member_only,
                "unit_price": product.unit_price,
                "unit_measure": product.unit_measure,
                "distance_km": None,
            },
            "last_updated": price.price_last_changed_at.isoformat(),
            "discount_pct": discount_pct,
        }


@router.get("/{product_id}/price-history", response_model=PriceHistoryResponse)
async def product_price_history(
    product_id: UUID,
    store_id: Optional[UUID] = Query(None),
    days: int = Query(default=90, ge=7, le=365),
) -> PriceHistoryResponse:
    async with get_async_session() as session:
        cache_key = f"price_history:{product_id}:{store_id}:{days}"

        async def producer() -> dict:
            # Verify product exists
            prod_result = await session.execute(
                select(Product.id, Product.name).where(Product.id == product_id)
            )
            product_row = prod_result.one_or_none()
            if not product_row:
                raise HTTPException(status_code=404, detail="Product not found")

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query = (
                select(PriceHistory, Store.name.label("store_name"), Store.chain)
                .join(Store, PriceHistory.store_id == Store.id)
                .where(
                    PriceHistory.product_id == product_id,
                    PriceHistory.recorded_at >= cutoff,
                )
                .order_by(PriceHistory.recorded_at.asc())
            )
            if store_id:
                query = query.where(PriceHistory.store_id == store_id)

            result = await session.execute(query)
            rows = result.all()

            # Group by store
            store_groups: dict[str, dict] = {}
            for row in rows:
                ph = row[0]
                sid = str(ph.store_id)
                if sid not in store_groups:
                    store_groups[sid] = {
                        "store_id": sid,
                        "store_name": row.store_name,
                        "chain": row.chain,
                        "data_points": [],
                    }
                store_groups[sid]["data_points"].append({
                    "price_nzd": ph.price_nzd,
                    "promo_price_nzd": ph.promo_price_nzd,
                    "is_member_only": ph.is_member_only,
                    "recorded_at": ph.recorded_at.isoformat(),
                })

            return {
                "product_id": str(product_row.id),
                "product_name": product_row.name,
                "stores": list(store_groups.values()),
            }

        payload = await cached_json(cache_key, 3600, producer)
        return PriceHistoryResponse.parse_obj(payload)


@router.get("/{product_id}", response_model=ProductDetailSchema)
async def product_detail(product_id: UUID) -> ProductDetailSchema:
    async with get_async_session() as session:
        cache_key = f"product_detail:{product_id}"

        async def producer() -> dict:
            try:
                product = await fetch_product_detail(session, product_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return json.loads(product.json())

        payload = await cached_json(cache_key, settings.cache_ttl_product_detail, producer)
        return ProductDetailSchema.parse_obj(payload)


# --- Batch resolve: resolve multiple search terms to best-match products ---

limiter = get_limiter()


class BatchResolveRequest(BaseModel):
    queries: list[str] = Field(..., min_length=1, max_length=30)
    lat: float
    lon: float
    radius_km: float = Field(default=5.0, le=10.0)


class ResolvedProduct(BaseModel):
    query: str
    product_id: str | None = None
    name: str | None = None
    brand: str | None = None
    size: str | None = None
    chain: str | None = None
    image_url: str | None = None
    department: str | None = None


class BatchResolveResponse(BaseModel):
    results: list[ResolvedProduct]
    resolved: int
    total: int


@router.post("/batch-resolve", response_model=BatchResolveResponse)
@limiter.limit("10/minute")
async def batch_resolve(request: Request, body: BatchResolveRequest) -> BatchResolveResponse:
    """Resolve a list of search terms to best-match products near a location.

    Used for loading preset trolleys — each query term is matched to the
    cheapest unique product within radius, one DB query per term.
    """
    if not (-47 <= body.lat <= -34 and 165 <= body.lon <= 179):
        raise HTTPException(status_code=400, detail="Location must be within New Zealand")

    results: list[ResolvedProduct] = []
    resolved = 0

    async with get_async_session() as session:
        for q in body.queries:
            q_clean = q.strip()
            if not q_clean:
                results.append(ResolvedProduct(query=q))
                continue

            try:
                params = ProductQueryParams(
                    q=q_clean,
                    lat=body.lat,
                    lon=body.lon,
                    radius_km=body.radius_km,
                    unique_products=True,
                    page=1,
                    page_size=1,
                    sort="total_price",
                    member_prices=True,
                )
                response = await fetch_products(session, params)
                if response.items:
                    p = response.items[0]
                    results.append(ResolvedProduct(
                        query=q_clean,
                        product_id=str(p.id),
                        name=p.name,
                        brand=p.brand,
                        size=p.size,
                        chain=p.chain,
                        image_url=p.image_url,
                        department=p.department,
                    ))
                    resolved += 1
                else:
                    results.append(ResolvedProduct(query=q_clean))
            except Exception:
                logger.debug("Batch resolve failed for query %r", q_clean, exc_info=True)
                results.append(ResolvedProduct(query=q_clean))

    return BatchResolveResponse(results=results, resolved=resolved, total=len(body.queries))
