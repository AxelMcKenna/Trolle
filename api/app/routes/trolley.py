from __future__ import annotations

import hashlib
import json
import logging

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.supabase_auth import UserContext, optional_user, require_user
from app.db.models import Product, TrolleyComparison
from app.db.session import get_async_session, async_transaction
from app.middleware import get_limiter
from app.schemas.trolley import (
    TrolleyCompareRequest,
    TrolleyCompareResponse,
    TrolleySuggestionsRequest,
    TrolleySuggestionsResponse,
)
from app.services.cache import cached_json
from app.services.matching import find_store_suggestions
from app.services.trolley import compare_trolley

logger = logging.getLogger(__name__)
settings = get_settings()
limiter = get_limiter()

router = APIRouter(prefix="/trolley", tags=["trolley"])


def _trolley_cache_key(request: TrolleyCompareRequest, user_id: Optional[str] = None) -> str:
    """Build a deterministic cache key for trolley comparison."""
    items_sorted = sorted(
        [{"pid": str(i.product_id), "qty": i.quantity} for i in request.items],
        key=lambda x: x["pid"],
    )
    raw = json.dumps({
        "items": items_sorted,
        "lat": round(request.lat, 2),
        "lon": round(request.lon, 2),
        "radius": request.radius_km,
        "loyalty": request.loyalty_cards,
        "uid": user_id,
    }, sort_keys=True)
    return f"trolley_compare:{hashlib.md5(raw.encode()).hexdigest()}"


@router.post("/compare", response_model=TrolleyCompareResponse)
@limiter.limit("30/minute")
async def trolley_compare(
    request: Request,
    body: TrolleyCompareRequest,
    user: Optional[UserContext] = Depends(optional_user),
) -> TrolleyCompareResponse:
    """Compare trolley items across nearby stores."""
    async with get_async_session() as session:
        try:
            cache_key = _trolley_cache_key(body, user_id=user.id if user else None)

            async def producer() -> dict:
                r = await compare_trolley(
                    session,
                    items=[
                        {"product_id": item.product_id, "quantity": item.quantity}
                        for item in body.items
                    ],
                    lat=body.lat,
                    lon=body.lon,
                    radius_km=body.radius_km,
                    loyalty_cards=body.loyalty_cards,
                )
                return r

            result = await cached_json(cache_key, settings.cache_ttl_trolley_compare, producer)

            # Persist comparison for authenticated users (fire-and-forget)
            if user and result.get("stores"):
                try:
                    stores = result["stores"]
                    cheapest = stores[0] if stores else None
                    most_expensive = max(stores, key=lambda s: s["estimated_total"]) if stores else None
                    if cheapest and most_expensive:
                        import uuid as uuid_mod
                        async with async_transaction() as tx:
                            tx.add(TrolleyComparison(
                                user_id=uuid_mod.UUID(user.id),
                                cheapest_store_name=cheapest.get("store_name"),
                                cheapest_total=cheapest["estimated_total"],
                                most_expensive_total=most_expensive["estimated_total"],
                                savings=round(most_expensive["estimated_total"] - cheapest["estimated_total"], 2),
                                item_count=len(body.items),
                            ))
                except Exception:
                    logger.debug("Failed to persist trolley comparison", exc_info=True)

            return TrolleyCompareResponse(**result)
        except HTTPException:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            logger.exception("Trolley comparison failed: %s", exc)
            raise HTTPException(status_code=500, detail="Trolley comparison failed")
        except Exception as exc:
            logger.exception("Unexpected trolley comparison error: %s", exc)
            raise HTTPException(status_code=500, detail="Trolley comparison failed")


@router.post("/suggestions", response_model=TrolleySuggestionsResponse)
@limiter.limit("30/minute")
async def trolley_suggestions(request: Request, body: TrolleySuggestionsRequest) -> TrolleySuggestionsResponse:
    """Get product suggestions for unavailable items at a specific store."""
    async with get_async_session() as session:
        try:
            # Load source products
            product_ids = [item.product_id for item in body.items]
            result = await session.execute(
                select(Product).where(Product.id.in_(product_ids))
            )
            products = {p.id: p for p in result.scalars().all()}

            suggestion_items = []
            for item in body.items:
                product = products.get(item.product_id)
                if not product:
                    suggestion_items.append({
                        "source_product_id": str(item.product_id),
                        "suggestions": [],
                    })
                    continue

                suggestions = await find_store_suggestions(
                    session,
                    product_name=product.name,
                    product_brand=product.brand,
                    product_size=product.size,
                    product_department=product.department,
                    product_subcategory=product.subcategory,
                    source_product_id=product.id,
                    store_id=body.store_id,
                    limit=3,
                )
                suggestion_items.append({
                    "source_product_id": str(item.product_id),
                    "suggestions": suggestions,
                })

            return TrolleySuggestionsResponse(items=suggestion_items)
        except HTTPException:
            raise
        except (ValueError, KeyError) as exc:
            logger.exception("Trolley suggestions failed: %s", exc)
            raise HTTPException(status_code=500, detail="Trolley suggestions failed")


# --- History & Savings ---

from pydantic import BaseModel


class TrolleyStatsResponse(BaseModel):
    total_comparisons: int
    total_savings: float
    average_savings: float
    most_used_store: str | None = None
    comparisons_this_month: int = 0
    savings_this_month: float = 0.0


class TrolleyHistoryItem(BaseModel):
    id: str
    cheapest_store_name: str | None
    cheapest_total: float
    most_expensive_total: float
    savings: float
    item_count: int
    created_at: str


class TrolleyHistoryResponse(BaseModel):
    items: list[TrolleyHistoryItem]
    count: int


@router.get("/history/stats", response_model=TrolleyStatsResponse)
async def trolley_history_stats(
    user: UserContext = Depends(require_user),
) -> TrolleyStatsResponse:
    """Get aggregate trolley comparison stats for the current user."""
    import uuid as uuid_mod
    from datetime import datetime, timezone

    user_uuid = uuid_mod.UUID(user.id)
    month_start = datetime.now(tz=timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async with get_async_session() as session:
        # All-time stats
        result = await session.execute(
            select(
                func.count().label("total"),
                func.coalesce(func.sum(TrolleyComparison.savings), 0).label("total_savings"),
                func.coalesce(func.avg(TrolleyComparison.savings), 0).label("avg_savings"),
            ).where(TrolleyComparison.user_id == user_uuid)
        )
        row = result.one()

        # Most used store (mode of cheapest_store_name)
        store_result = await session.execute(
            select(
                TrolleyComparison.cheapest_store_name,
                func.count().label("cnt"),
            )
            .where(TrolleyComparison.user_id == user_uuid)
            .where(TrolleyComparison.cheapest_store_name.is_not(None))
            .group_by(TrolleyComparison.cheapest_store_name)
            .order_by(func.count().desc())
            .limit(1)
        )
        store_row = store_result.first()
        most_used = store_row[0] if store_row else None

        # This month stats
        month_result = await session.execute(
            select(
                func.count().label("total"),
                func.coalesce(func.sum(TrolleyComparison.savings), 0).label("total_savings"),
            )
            .where(TrolleyComparison.user_id == user_uuid)
            .where(TrolleyComparison.created_at >= month_start)
        )
        month_row = month_result.one()

        return TrolleyStatsResponse(
            total_comparisons=row.total,
            total_savings=round(float(row.total_savings), 2),
            average_savings=round(float(row.avg_savings), 2),
            most_used_store=most_used,
            comparisons_this_month=month_row.total,
            savings_this_month=round(float(month_row.total_savings), 2),
        )


@router.get("/history", response_model=TrolleyHistoryResponse)
async def trolley_history(
    user: UserContext = Depends(require_user),
    limit: int = 20,
    offset: int = 0,
) -> TrolleyHistoryResponse:
    """Get recent trolley comparisons for the current user."""
    import uuid as uuid_mod

    user_uuid = uuid_mod.UUID(user.id)

    async with get_async_session() as session:
        count_result = await session.execute(
            select(func.count()).select_from(TrolleyComparison)
            .where(TrolleyComparison.user_id == user_uuid)
        )
        count = count_result.scalar_one()

        result = await session.execute(
            select(TrolleyComparison)
            .where(TrolleyComparison.user_id == user_uuid)
            .order_by(TrolleyComparison.created_at.desc())
            .limit(min(limit, 50))
            .offset(offset)
        )
        rows = result.scalars().all()

        return TrolleyHistoryResponse(
            items=[
                TrolleyHistoryItem(
                    id=str(r.id),
                    cheapest_store_name=r.cheapest_store_name,
                    cheapest_total=r.cheapest_total,
                    most_expensive_total=r.most_expensive_total,
                    savings=r.savings,
                    item_count=r.item_count,
                    created_at=r.created_at.isoformat(),
                )
                for r in rows
            ],
            count=count,
        )


class GlobalStatsResponse(BaseModel):
    total_comparisons: int
    total_savings: float
    average_savings: float


@router.get("/stats/global", response_model=GlobalStatsResponse)
async def trolley_global_stats() -> GlobalStatsResponse:
    """Get aggregate savings stats across all users. No auth required. Cached 1 hour."""
    async def producer() -> dict:
        async with get_async_session() as session:
            result = await session.execute(
                select(
                    func.count().label("total"),
                    func.coalesce(func.sum(TrolleyComparison.savings), 0).label("total_savings"),
                    func.coalesce(func.avg(TrolleyComparison.savings), 0).label("avg_savings"),
                )
            )
            row = result.one()
            return {
                "total_comparisons": row.total,
                "total_savings": round(float(row.total_savings), 2),
                "average_savings": round(float(row.avg_savings), 2),
            }

    data = await cached_json("trolley_global_stats", 3600, producer)
    return GlobalStatsResponse(**data)
