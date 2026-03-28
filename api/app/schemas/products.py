from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PriceSchema(BaseModel):
    store_id: UUID
    store_name: str
    chain: str
    price_nzd: float
    promo_price_nzd: Optional[float]
    promo_text: Optional[str]
    promo_ends_at: Optional[datetime]
    unit_price: Optional[float]
    unit_measure: Optional[str]
    is_member_only: bool
    is_stale: bool = False
    distance_km: Optional[float]


class ProductSchema(BaseModel):
    id: UUID
    name: str
    brand: Optional[str]
    category: Optional[str]
    chain: str
    size: Optional[str]
    department: Optional[str]
    subcategory: Optional[str]
    image_url: Optional[str]
    product_url: Optional[str]
    price: PriceSchema
    last_updated: datetime


class ProductDetailSchema(BaseModel):
    id: UUID
    name: str
    brand: Optional[str]
    category: Optional[str]
    chain: str
    size: Optional[str]
    department: Optional[str]
    subcategory: Optional[str]
    image_url: Optional[str]
    product_url: Optional[str]
    description: Optional[str] = None
    prices: list[PriceSchema]
    last_updated: datetime


class ProductListResponse(BaseModel):
    items: list[ProductSchema]
    total: int
    page: int
    page_size: int


class StoreSchema(BaseModel):
    id: UUID
    name: str
    chain: str
    lat: Optional[float]
    lon: Optional[float]
    address: Optional[str]
    region: Optional[str]
    distance_km: Optional[float]
    click_collect: Optional[bool] = None
    delivery: Optional[bool] = None
    delivery_fee_nzd: Optional[float] = None
    cc_fee_nzd: Optional[float] = None
    min_order_nzd: Optional[float] = None
    free_delivery_threshold_nzd: Optional[float] = None


class StoreListResponse(BaseModel):
    items: list[StoreSchema]


class PriceHistoryPoint(BaseModel):
    price_nzd: float
    promo_price_nzd: Optional[float]
    is_member_only: bool
    recorded_at: datetime


class StoreHistoryGroup(BaseModel):
    store_id: UUID
    store_name: str
    chain: str
    data_points: list[PriceHistoryPoint]


class PriceHistoryResponse(BaseModel):
    product_id: UUID
    product_name: str
    stores: list[StoreHistoryGroup]


__all__ = [
    "PriceSchema",
    "ProductSchema",
    "ProductDetailSchema",
    "ProductListResponse",
    "StoreSchema",
    "StoreListResponse",
    "PriceHistoryPoint",
    "StoreHistoryGroup",
    "PriceHistoryResponse",
]
