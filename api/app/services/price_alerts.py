from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, Price, PriceAlert, Product

logger = logging.getLogger(__name__)


async def check_triggered_alerts(session: AsyncSession) -> int:
    """Check all active price alerts and trigger those whose target price has been met.

    Returns the number of newly triggered alerts.
    """
    now = datetime.now(timezone.utc)

    # Fetch active alerts joined with current prices
    query = (
        select(PriceAlert, Price, Product.name.label("product_name"))
        .join(Product, PriceAlert.product_id == Product.id)
        .join(
            Price,
            and_(
                Price.product_id == PriceAlert.product_id,
                or_(
                    PriceAlert.store_id.is_(None),
                    Price.store_id == PriceAlert.store_id,
                ),
            ),
        )
        .where(PriceAlert.is_active.is_(True), PriceAlert.triggered_at.is_(None))
    )

    result = await session.execute(query)
    rows = result.all()

    triggered_count = 0
    triggered_alert_ids: set[str] = set()

    for row in rows:
        alert: PriceAlert = row[0]
        price: Price = row[1]
        product_name: str = row.product_name

        # Skip if already triggered in this batch (may match multiple stores)
        if str(alert.id) in triggered_alert_ids:
            continue

        # Effective price: promo if active, else regular
        effective = price.price_nzd
        if price.promo_price_nzd is not None:
            if price.promo_ends_at is None or price.promo_ends_at > now:
                effective = price.promo_price_nzd

        if effective <= alert.target_price:
            alert.triggered_at = now
            alert.is_active = False
            triggered_alert_ids.add(str(alert.id))

            notification = Notification(
                user_id=alert.user_id,
                alert_id=alert.id,
                title=f"Price drop: {product_name}",
                message=f"{product_name} is now ${effective:.2f} (your target: ${alert.target_price:.2f})",
            )
            session.add(notification)
            triggered_count += 1

    return triggered_count
