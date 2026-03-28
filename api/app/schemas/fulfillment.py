"""Pydantic schemas for fulfillment / delivery slot endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SlotDetail(BaseModel):
    slot_date: date
    slot_start: datetime
    slot_end: datetime
    is_available: bool
    price_nzd: Optional[float]


class SlotAvailability(BaseModel):
    fulfillment_type: str
    has_slots_available: bool
    next_available_slot: Optional[datetime]
    slots: list[SlotDetail]


class StoreSlotResponse(BaseModel):
    store_id: UUID
    store_name: str
    chain: str
    delivery_slots: Optional[SlotAvailability] = None
    click_collect_slots: Optional[SlotAvailability] = None


class NearbyStoreSlotSummary(BaseModel):
    store_id: UUID
    store_name: str
    chain: str
    distance_km: float
    delivery_available: Optional[bool] = None
    cc_available: Optional[bool] = None
    next_delivery_slot: Optional[datetime] = None
    next_cc_slot: Optional[datetime] = None


class NearbySlotResponse(BaseModel):
    items: list[NearbyStoreSlotSummary]


__all__ = [
    "SlotDetail",
    "SlotAvailability",
    "StoreSlotResponse",
    "NearbyStoreSlotSummary",
    "NearbySlotResponse",
]
