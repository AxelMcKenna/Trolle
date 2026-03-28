from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app.core.supabase_auth import UserContext, require_user
from app.db.models import Notification, Price, PriceAlert, Product, Store
from app.db.session import async_transaction, get_async_session
from app.middleware import get_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])
limiter = get_limiter()

MAX_ALERTS_PER_USER = 50


# --- Schemas ---

class CreateAlertRequest(BaseModel):
    product_id: UUID
    store_id: Optional[UUID] = None
    target_price: float = Field(gt=0)


class PriceAlertResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_image_url: Optional[str]
    chain: str
    store_id: Optional[str]
    store_name: Optional[str]
    target_price: float
    current_price: float
    is_active: bool
    triggered_at: Optional[datetime]
    created_at: datetime


class AlertListResponse(BaseModel):
    items: list[PriceAlertResponse]
    count: int


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    is_read: bool
    alert_id: Optional[str]
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class MarkReadRequest(BaseModel):
    notification_ids: Optional[list[UUID]] = None
    all: bool = False


# --- Alert endpoints ---

@router.post("", response_model=PriceAlertResponse)
@limiter.limit("10/minute")
async def create_alert(
    request: Request,
    body: CreateAlertRequest,
    user: UserContext = Depends(require_user),
) -> PriceAlertResponse:
    async with async_transaction() as session:
        # Check limit
        count_result = await session.execute(
            select(func.count(PriceAlert.id)).where(
                PriceAlert.user_id == user.id,
                PriceAlert.is_active.is_(True),
            )
        )
        if (count_result.scalar() or 0) >= MAX_ALERTS_PER_USER:
            raise HTTPException(status_code=400, detail=f"Maximum {MAX_ALERTS_PER_USER} active alerts allowed")

        # Check for existing active alert on same product/store
        dup_query = select(PriceAlert).where(
            PriceAlert.user_id == user.id,
            PriceAlert.product_id == body.product_id,
            PriceAlert.is_active.is_(True),
        )
        if body.store_id:
            dup_query = dup_query.where(PriceAlert.store_id == body.store_id)
        else:
            dup_query = dup_query.where(PriceAlert.store_id.is_(None))

        existing = (await session.execute(dup_query)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="You already have an active alert for this product")

        # Verify product exists and get current info
        product = (await session.execute(
            select(Product).where(Product.id == body.product_id)
        )).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Get current price
        price_query = select(Price).where(Price.product_id == body.product_id)
        if body.store_id:
            price_query = price_query.where(Price.store_id == body.store_id)
        price_query = price_query.order_by(Price.price_nzd.asc()).limit(1)
        price_row = (await session.execute(price_query)).scalar_one_or_none()
        current_price = price_row.promo_price_nzd or price_row.price_nzd if price_row else 0.0

        # Get store name if store_id provided
        store_name = None
        if body.store_id:
            store = (await session.execute(
                select(Store.name).where(Store.id == body.store_id)
            )).scalar_one_or_none()
            store_name = store

        alert = PriceAlert(
            user_id=user.id,
            product_id=body.product_id,
            store_id=body.store_id,
            target_price=body.target_price,
        )
        session.add(alert)
        await session.flush()

        return PriceAlertResponse(
            id=str(alert.id),
            product_id=str(product.id),
            product_name=product.name,
            product_image_url=product.image_url,
            chain=product.chain,
            store_id=str(body.store_id) if body.store_id else None,
            store_name=store_name,
            target_price=body.target_price,
            current_price=current_price,
            is_active=True,
            triggered_at=None,
            created_at=alert.created_at,
        )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    user: UserContext = Depends(require_user),
    active_only: bool = Query(default=False),
) -> AlertListResponse:
    async with get_async_session() as session:
        query = (
            select(PriceAlert, Product, Store.name.label("store_name"))
            .join(Product, PriceAlert.product_id == Product.id)
            .outerjoin(Store, PriceAlert.store_id == Store.id)
            .where(PriceAlert.user_id == user.id)
            .order_by(PriceAlert.created_at.desc())
        )
        if active_only:
            query = query.where(PriceAlert.is_active.is_(True))

        result = await session.execute(query)
        rows = result.all()

        # Batch-fetch current prices for all alert products
        product_ids = list({row[0].product_id for row in rows})
        price_map: dict[str, float] = {}
        if product_ids:
            prices_result = await session.execute(
                select(
                    Price.product_id,
                    func.min(Price.price_nzd).label("min_price"),
                ).where(Price.product_id.in_(product_ids)).group_by(Price.product_id)
            )
            for pr in prices_result:
                price_map[str(pr.product_id)] = pr.min_price

        items = []
        for row in rows:
            alert: PriceAlert = row[0]
            product: Product = row[1]
            items.append(PriceAlertResponse(
                id=str(alert.id),
                product_id=str(product.id),
                product_name=product.name,
                product_image_url=product.image_url,
                chain=product.chain,
                store_id=str(alert.store_id) if alert.store_id else None,
                store_name=row.store_name,
                target_price=alert.target_price,
                current_price=price_map.get(str(product.id), 0.0),
                is_active=alert.is_active,
                triggered_at=alert.triggered_at,
                created_at=alert.created_at,
            ))

        return AlertListResponse(items=items, count=len(items))


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: UUID,
    user: UserContext = Depends(require_user),
) -> dict:
    async with async_transaction() as session:
        alert = (await session.execute(
            select(PriceAlert).where(
                PriceAlert.id == alert_id,
                PriceAlert.user_id == user.id,
            )
        )).scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.is_active = False
        return {"status": "ok"}


# --- Notification endpoints ---

@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    user: UserContext = Depends(require_user),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
) -> NotificationListResponse:
    async with get_async_session() as session:
        query = (
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if unread_only:
            query = query.where(Notification.is_read.is_(False))

        result = await session.execute(query)
        notifications = result.scalars().all()

        # Unread count
        unread_result = await session.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
        )
        unread_count = unread_result.scalar() or 0

        return NotificationListResponse(
            items=[
                NotificationResponse(
                    id=str(n.id),
                    title=n.title,
                    message=n.message,
                    is_read=n.is_read,
                    alert_id=str(n.alert_id) if n.alert_id else None,
                    created_at=n.created_at,
                )
                for n in notifications
            ],
            unread_count=unread_count,
        )


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    body: MarkReadRequest,
    user: UserContext = Depends(require_user),
) -> dict:
    async with async_transaction() as session:
        if body.all:
            await session.execute(
                update(Notification)
                .where(Notification.user_id == user.id, Notification.is_read.is_(False))
                .values(is_read=True)
            )
        elif body.notification_ids:
            await session.execute(
                update(Notification)
                .where(
                    Notification.user_id == user.id,
                    Notification.id.in_(body.notification_ids),
                )
                .values(is_read=True)
            )
        return {"status": "ok"}
