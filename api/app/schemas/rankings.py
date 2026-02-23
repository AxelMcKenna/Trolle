from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class RankedStore(BaseModel):
    store_id: UUID
    store_name: str
    chain: str
    distance_km: float
    price_index: float = Field(description="100 = cheapest store, higher = more expensive")
    matched_products: int
    total_category_products: int
    avg_effective_price: float
    cheapest_count: int


class StoreRankingResponse(BaseModel):
    category: str
    stores: list[RankedStore]
    total_comparison_products: int


__all__ = ["RankedStore", "StoreRankingResponse"]
