from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class TrolleyItem(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=99, default=1)


class TrolleyCompareRequest(BaseModel):
    items: list[TrolleyItem] = Field(..., min_length=1, max_length=50)
    lat: float
    lon: float
    radius_km: float = Field(ge=1, le=10)

    @validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not (-47 <= v <= -34):
            raise ValueError("Latitude must be within New Zealand bounds (-47 to -34)")
        return v

    @validator("lon")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if not (165 <= v <= 179):
            raise ValueError("Longitude must be within New Zealand bounds (165 to 179)")
        return v


class TrolleyStoreItem(BaseModel):
    source_product_id: str
    source_product_name: str
    quantity: int
    available: bool
    matched_product_id: Optional[str]
    matched_product_name: Optional[str]
    price: Optional[float]
    line_total: Optional[float]


class TrolleyStoreBreakdown(BaseModel):
    store_id: str
    store_name: str
    chain: str
    distance_km: float
    estimated_total: float
    items_available: int
    items_total: int
    is_complete: bool
    items: list[TrolleyStoreItem]


class TrolleySourceItem(BaseModel):
    product_id: str
    name: str
    brand: Optional[str]
    size: Optional[str]
    chain: str
    image_url: Optional[str]
    department: Optional[str]
    quantity: int


class TrolleySummary(BaseModel):
    total_items: int
    total_stores: int = 0
    complete_stores: int = 0


class TrolleyCompareResponse(BaseModel):
    stores: list[TrolleyStoreBreakdown]
    items: list[TrolleySourceItem]
    summary: TrolleySummary


class SuggestionProduct(BaseModel):
    product_id: str
    name: str
    brand: Optional[str]
    size: Optional[str]
    image_url: Optional[str]
    price_nzd: float
    promo_price_nzd: Optional[float]
    similarity: float


class SuggestionItem(BaseModel):
    source_product_id: str
    suggestions: list[SuggestionProduct]


class TrolleySuggestionsRequest(BaseModel):
    store_id: UUID
    items: list[TrolleyItem] = Field(..., min_length=1, max_length=50)


class TrolleySuggestionsResponse(BaseModel):
    items: list[SuggestionItem]


__all__ = [
    "TrolleyItem",
    "TrolleyCompareRequest",
    "TrolleyCompareResponse",
    "TrolleyStoreBreakdown",
    "TrolleyStoreItem",
    "TrolleySourceItem",
    "TrolleySummary",
    "SuggestionProduct",
    "SuggestionItem",
    "TrolleySuggestionsRequest",
    "TrolleySuggestionsResponse",
]
