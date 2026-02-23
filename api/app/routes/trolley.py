from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from sqlalchemy import select

from app.db.models import Product
from app.db.session import get_async_session
from app.schemas.trolley import (
    TrolleyCompareRequest,
    TrolleyCompareResponse,
    TrolleySuggestionsRequest,
    TrolleySuggestionsResponse,
)
from app.services.matching import find_store_suggestions
from app.services.trolley import compare_trolley

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trolley", tags=["trolley"])


@router.post("/compare", response_model=TrolleyCompareResponse)
async def trolley_compare(request: TrolleyCompareRequest) -> TrolleyCompareResponse:
    """Compare trolley items across nearby stores."""
    async with get_async_session() as session:
        try:
            result = await compare_trolley(
                session,
                items=[
                    {"product_id": item.product_id, "quantity": item.quantity}
                    for item in request.items
                ],
                lat=request.lat,
                lon=request.lon,
                radius_km=request.radius_km,
            )
            return TrolleyCompareResponse(**result)
        except Exception:
            logger.exception("Trolley comparison failed")
            raise HTTPException(status_code=500, detail="Trolley comparison failed")


@router.post("/suggestions", response_model=TrolleySuggestionsResponse)
async def trolley_suggestions(request: TrolleySuggestionsRequest) -> TrolleySuggestionsResponse:
    """Get product suggestions for unavailable items at a specific store."""
    async with get_async_session() as session:
        try:
            # Load source products
            product_ids = [item.product_id for item in request.items]
            result = await session.execute(
                select(Product).where(Product.id.in_(product_ids))
            )
            products = {p.id: p for p in result.scalars().all()}

            suggestion_items = []
            for item in request.items:
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
                    store_id=request.store_id,
                    limit=3,
                )
                suggestion_items.append({
                    "source_product_id": str(item.product_id),
                    "suggestions": suggestions,
                })

            return TrolleySuggestionsResponse(items=suggestion_items)
        except Exception:
            logger.exception("Trolley suggestions failed")
            raise HTTPException(status_code=500, detail="Trolley suggestions failed")
