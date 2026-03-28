from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from pydantic import ValidationError

from app.core.config import get_settings
from app.db.session import get_async_session
from app.middleware import get_limiter
from app.schemas.products import ProductDetailSchema, ProductListResponse
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
