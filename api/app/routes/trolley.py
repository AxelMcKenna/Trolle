from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.db.session import get_async_session
from app.schemas.trolley import TrolleyCompareRequest, TrolleyCompareResponse
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
