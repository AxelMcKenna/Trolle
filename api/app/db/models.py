from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Computed, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

try:
    from pgvector.sqlalchemy import Vector

    _VECTOR_TYPE = Vector(384)
except ImportError:
    _VECTOR_TYPE = None

from .base import Base

UUID_TYPE = UUID(as_uuid=True)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    api_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Store ID from API (e.g., PAK'nSAVE, New World APIs)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    chain: Mapped[str] = mapped_column(String(64), nullable=False)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geog: Mapped[Optional[object]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        Computed(
            "CASE WHEN lat IS NULL OR lon IS NULL THEN NULL "
            "ELSE ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography END",
            persisted=True,
        ),
        nullable=True,
    )
    address: Mapped[Optional[str]] = mapped_column(String(255))
    region: Mapped[Optional[str]] = mapped_column(String(64))
    url: Mapped[Optional[str]] = mapped_column(String(255))

    # Fulfillment capabilities (NULL = unknown, False = confirmed unavailable)
    click_collect: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    delivery: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    delivery_fee_nzd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_order_nzd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cc_fee_nzd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    free_delivery_threshold_nzd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fulfillment_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    prices: Mapped[list["Price"]] = relationship(back_populates="store")

    __table_args__ = (
        UniqueConstraint("chain", "name", name="uq_store_chain_name"),
        UniqueConstraint("chain", "api_id", name="uq_store_chain_api_id"),
        Index("ix_store_chain", "chain"),  # For chain filtering queries
        Index("ix_store_geog", "geog", postgresql_using="gist"),  # Spatial queries
        Index("ix_store_fulfillment", "chain", "delivery", "click_collect"),
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    chain: Mapped[str] = mapped_column(String(64), nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(128))
    category: Mapped[Optional[str]] = mapped_column(String(64))
    size: Mapped[Optional[str]] = mapped_column(String(64))
    department: Mapped[Optional[str]] = mapped_column(String(64))
    subcategory: Mapped[Optional[str]] = mapped_column(String(128))
    unit_price: Mapped[Optional[float]] = mapped_column(Float)
    unit_measure: Mapped[Optional[str]] = mapped_column(String(16))
    image_url: Mapped[Optional[str]] = mapped_column(String(512))
    product_url: Mapped[Optional[str]] = mapped_column(String(512))
    volume_ml: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pack_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    normalized_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_brand: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    prices: Mapped[list["Price"]] = relationship(back_populates="product")

    __table_args__ = (
        UniqueConstraint("chain", "source_product_id", name="uq_product_source"),
        Index("ix_product_chain", "chain"),  # For chain filtering queries
        Index("ix_product_department", "department"),
        Index("ix_product_subcategory", "subcategory"),
        Index("ix_product_volume_ml", "volume_ml"),
        Index("ix_product_weight_g", "weight_g"),
        Index("ix_product_dept_volume", "department", "volume_ml"),
        Index("ix_product_dept_weight", "department", "weight_g"),
    )


# Add embedding column only when pgvector is installed
if _VECTOR_TYPE is not None:
    from sqlalchemy import Column

    Product.embedding = Column("embedding", _VECTOR_TYPE, nullable=True)


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NZD")
    price_nzd: Mapped[float] = mapped_column(Float, nullable=False)
    promo_price_nzd: Mapped[Optional[float]] = mapped_column(Float)
    promo_text: Mapped[Optional[str]] = mapped_column(String(255))
    promo_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_last_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_member_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    product: Mapped[Product] = relationship(back_populates="prices")
    store: Mapped[Store] = relationship(back_populates="prices")

    __table_args__ = (
        UniqueConstraint("product_id", "store_id", name="uq_price_product_store"),
        Index("ix_price_price_nzd", "price_nzd"),
        Index("ix_price_promo_price_nzd", "promo_price_nzd"),
        Index("ix_price_last_changed", "price_last_changed_at"),
        Index("ix_price_product_id", "product_id"),  # FK index for JOINs
        Index("ix_price_store_id", "store_id"),  # FK index for JOINs
        Index("ix_price_last_seen", "last_seen_at"),  # For cleanup queries
        Index("ix_price_product_store", "product_id", "store_id"),  # Composite for JOIN + filter
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    price_nzd: Mapped[float] = mapped_column(Float, nullable=False)
    promo_price_nzd: Mapped[Optional[float]] = mapped_column(Float)
    is_member_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_price_history_product_store_recorded", "product_id", "store_id", "recorded_at"),
        Index("ix_price_history_recorded_at", "recorded_at"),
    )


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024))
    servings: Mapped[int] = mapped_column(default=4)
    image_url: Mapped[Optional[str]] = mapped_column(String(512))
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(255))
    share_token: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_recipe_is_public", "is_public"),
        Index("ix_recipe_created_by", "created_by"),
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Optional[float]] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    optional: Mapped[bool] = mapped_column(Boolean, default=False)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")

    __table_args__ = (
        Index("ix_recipe_ingredient_recipe_id", "recipe_id"),
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    chain: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    items_total: Mapped[int] = mapped_column(default=0)
    items_changed: Mapped[int] = mapped_column(default=0)
    items_failed: Mapped[int] = mapped_column(default=0)
    log_url: Mapped[Optional[str]] = mapped_column(String(255))

    __table_args__ = (
        Index("ix_ingestion_run_chain_status", "chain", "status"),  # For status queries
        Index("ix_ingestion_run_chain_started", "chain", "started_at"),  # For recent run queries
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True)  # = auth.users.id
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    preferred_radius_km: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    loyalty_cards: Mapped[dict] = mapped_column(
        JSONB,
        default={"countdown": True, "new_world": True, "paknsave": True},
        nullable=False,
        server_default='{"countdown": true, "new_world": true, "paknsave": true}',
    )

    saved_trolleys: Mapped[list["SavedTrolley"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_recipes: Mapped[list["SavedRecipe"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    price_alerts: Mapped[list["PriceAlert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SavedTrolley(Base):
    __tablename__ = "saved_trolleys"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    items: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    share_token: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)

    user: Mapped[UserProfile] = relationship(back_populates="saved_trolleys")

    __table_args__ = (
        Index("ix_saved_trolleys_user", "user_id"),
    )


class SavedRecipe(Base):
    __tablename__ = "saved_recipes"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped[UserProfile] = relationship(back_populates="saved_recipes")
    recipe: Mapped[Recipe] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "recipe_id", name="uq_saved_recipe_user_recipe"),
        Index("ix_saved_recipes_user", "user_id"),
    )


class TrolleyComparison(Base):
    __tablename__ = "trolley_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    trolley_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("saved_trolleys.id", ondelete="SET NULL"), nullable=True
    )
    cheapest_store_name: Mapped[Optional[str]] = mapped_column(String(255))
    cheapest_total: Mapped[float] = mapped_column(Float, nullable=False)
    most_expensive_total: Mapped[float] = mapped_column(Float, nullable=False)
    savings: Mapped[float] = mapped_column(Float, nullable=False)
    item_count: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        Index("ix_trolley_comparisons_user", "user_id"),
    )


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[UserProfile] = relationship(back_populates="price_alerts")
    product: Mapped[Product] = relationship()
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_price_alerts_user", "user_id"),
        Index("ix_price_alerts_active_product", "product_id", "is_active"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("price_alerts.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[UserProfile] = relationship(back_populates="notifications")
    alert: Mapped[Optional[PriceAlert]] = relationship(back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )


class DeliverySlot(Base):
    __tablename__ = "delivery_slots"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    fulfillment_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "delivery" or "click_collect"
    slot_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    price_nzd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("store_id", "fulfillment_type", "slot_start", name="uq_delivery_slot"),
        Index("ix_delivery_slot_store_type_date", "store_id", "fulfillment_type", "slot_date"),
        Index("ix_delivery_slot_available", "store_id", "fulfillment_type", "is_available"),
    )


__all__ = [
    "Store", "Product", "Price", "PriceHistory", "IngestionRun",
    "Recipe", "RecipeIngredient",
    "UserProfile", "SavedTrolley", "SavedRecipe",
    "TrolleyComparison", "PriceAlert", "Notification",
    "DeliverySlot",
]
