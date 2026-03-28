"""Delivery and click-and-collect slot scrapers.

Lightweight scrapers that check fulfillment slot availability for each
chain.  Designed to run every ~2 hours (much more frequently than the
daily product scrapers) since slot availability is highly perishable.

Each chain subclass implements ``fetch_slots`` which returns raw slot
dicts for a single store.  The base ``run`` method handles DB upserts,
staleness cleanup, and updating Store capability flags.
"""
from __future__ import annotations

import abc
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import and_, delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import DeliverySlot, Store
from app.db.session import get_async_session

logger = logging.getLogger(__name__)

SLOT_SCRAPE_CONCURRENCY = 5  # max stores scraped concurrently
SLOT_STALE_DAYS = 7  # delete slots older than this


class SlotScraper(abc.ABC):
    """Abstract base for fulfillment slot scrapers."""

    chain: str

    @abc.abstractmethod
    async def fetch_slots(self, store: Store, client: httpx.AsyncClient) -> list[dict]:
        """Fetch slot data for a single store.

        Returns list of dicts with keys:
            fulfillment_type: "delivery" | "click_collect"
            slot_date: date
            slot_start: datetime (tz-aware)
            slot_end: datetime (tz-aware)
            is_available: bool
            price_nzd: float | None
        """
        ...

    async def run(self) -> int:
        """Scrape slots for all eligible stores of this chain.

        Returns the total number of slots upserted.
        """
        total_upserted = 0
        now = datetime.now(tz=timezone.utc)

        async with get_async_session() as session:
            # Find stores that might support online fulfillment
            query = (
                select(Store)
                .where(Store.chain == self.chain)
                .where(
                    # Include stores with confirmed capability or unknown (NULL)
                    ~and_(Store.delivery == False, Store.click_collect == False)  # noqa: E712
                )
            )
            result = await session.execute(query)
            stores = result.scalars().all()

        if not stores:
            logger.info(f"[{self.chain}] No eligible stores for slot scraping")
            return 0

        logger.info(f"[{self.chain}] Scraping slots for {len(stores)} stores")

        sem = asyncio.Semaphore(SLOT_SCRAPE_CONCURRENCY)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:

            async def _scrape_one(store: Store) -> int:
                async with sem:
                    try:
                        slots = await self.fetch_slots(store, client)
                    except Exception:
                        logger.debug(f"[{self.chain}] Slot fetch failed for {store.name}", exc_info=True)
                        return 0

                    if not slots:
                        return 0

                    return await self._upsert_slots(store, slots, now)

            results = await asyncio.gather(*[_scrape_one(s) for s in stores])
            total_upserted = sum(results)

        # Cleanup old slots
        async with get_async_session() as session:
            cutoff = now - timedelta(days=SLOT_STALE_DAYS)
            await session.execute(
                delete(DeliverySlot).where(DeliverySlot.slot_start < cutoff)
            )
            await session.commit()

        logger.info(f"[{self.chain}] Slot scraping complete: {total_upserted} slots upserted")
        return total_upserted

    async def _upsert_slots(self, store: Store, slots: list[dict], now: datetime) -> int:
        """Upsert slot records and update store capability flags."""
        has_delivery = False
        has_cc = False

        async with get_async_session() as session:
            for slot in slots:
                ft = slot["fulfillment_type"]
                if ft == "delivery":
                    has_delivery = True
                elif ft == "click_collect":
                    has_cc = True

                stmt = pg_insert(DeliverySlot.__table__).values(
                    store_id=store.id,
                    fulfillment_type=ft,
                    slot_date=slot["slot_date"],
                    slot_start=slot["slot_start"],
                    slot_end=slot["slot_end"],
                    is_available=slot["is_available"],
                    price_nzd=slot.get("price_nzd"),
                    scraped_at=now,
                ).on_conflict_do_update(
                    constraint="uq_delivery_slot",
                    set_={
                        "slot_end": slot["slot_end"],
                        "is_available": slot["is_available"],
                        "price_nzd": slot.get("price_nzd"),
                        "scraped_at": now,
                    },
                )
                await session.execute(stmt)

            # Update store capability flags based on what we found
            updates = {"fulfillment_updated_at": now}
            if has_delivery:
                updates["delivery"] = True
            if has_cc:
                updates["click_collect"] = True

            await session.execute(
                text(
                    "UPDATE stores SET "
                    + ", ".join(f"{k} = :{k}" for k in updates)
                    + " WHERE id = :store_id"
                ),
                {**updates, "store_id": store.id},
            )
            await session.commit()

        return len(slots)


class CountdownSlotScraper(SlotScraper):
    """Slot scraper for Woolworths NZ (formerly Countdown).

    Probes the fulfilment slot API at woolworths.co.nz for each
    online-capable store.
    """

    chain = "countdown"
    site_url = "https://www.woolworths.co.nz"

    async def fetch_slots(self, store: Store, client: httpx.AsyncClient) -> list[dict]:
        if not store.api_id:
            return []

        # Get session cookies
        cookies_resp = await client.get(
            self.site_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            },
        )
        cookies = dict(cookies_resp.cookies)
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

        # Fetch delivery slots
        headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "x-requested-with": "OnlineShopping.WebApp",
            "cookie": cookie_str,
        }

        slots: list[dict] = []

        for fulfillment_type, api_type in [("delivery", "Courier"), ("click_collect", "PickUp")]:
            try:
                resp = await client.get(
                    f"{self.site_url}/api/v1/fulfilment/slots?type={api_type}&storeId={store.api_id}",
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                for day in data.get("days", []):
                    date_str = day.get("date", "")
                    for slot in day.get("slots", []):
                        slot_start = slot.get("startTime")
                        slot_end = slot.get("endTime")
                        if not slot_start or not slot_end:
                            continue

                        try:
                            start_dt = datetime.fromisoformat(slot_start)
                            end_dt = datetime.fromisoformat(slot_end)
                            slot_date = start_dt.date()
                        except (ValueError, TypeError):
                            continue

                        slots.append({
                            "fulfillment_type": fulfillment_type,
                            "slot_date": slot_date,
                            "slot_start": start_dt,
                            "slot_end": end_dt,
                            "is_available": not slot.get("isFull", True),
                            "price_nzd": slot.get("price"),
                        })
            except Exception:
                logger.debug(f"Countdown slot fetch failed for {store.name} ({fulfillment_type})", exc_info=True)

        return slots


class FoodstuffsSlotScraper(SlotScraper):
    """Slot scraper for Foodstuffs chains (New World, PAK'nSAVE).

    Both chains share similar slot API infrastructure.
    """

    chain: str
    site_url: str

    async def _get_auth_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get a guest auth token from the site's Next.js API."""
        domain = self.site_url.split("//")[-1].split("/")[0]
        url = f"https://{domain}/api/user/get-current-user"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "origin": f"https://{domain}",
            "referer": f"https://{domain}/",
        }
        try:
            resp = await client.post(url, headers=headers, json={})
            resp.raise_for_status()
            data = resp.json()
            return data.get("access_token") or data.get("token")
        except Exception:
            logger.debug(f"Failed to get Foodstuffs auth token for {self.chain}", exc_info=True)
            return None

    async def fetch_slots(self, store: Store, client: httpx.AsyncClient) -> list[dict]:
        if not store.api_id:
            return []

        token = await self._get_auth_token(client)
        if not token:
            return []

        domain = self.site_url.split("//")[-1].split("/")[0]
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {token}",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "origin": f"https://{domain}",
        }

        slots: list[dict] = []

        for fulfillment_type, api_path in [
            ("click_collect", "click-and-collect"),
            ("delivery", "delivery"),
        ]:
            try:
                resp = await client.get(
                    f"https://{domain}/api/slots/{api_path}?storeId={store.api_id}",
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                for day in data.get("slots", data.get("days", [])):
                    for slot in day.get("slots", [day] if "startTime" in day else []):
                        slot_start = slot.get("startTime") or slot.get("start")
                        slot_end = slot.get("endTime") or slot.get("end")
                        if not slot_start or not slot_end:
                            continue

                        try:
                            start_dt = datetime.fromisoformat(slot_start)
                            end_dt = datetime.fromisoformat(slot_end)
                            slot_date = start_dt.date()
                        except (ValueError, TypeError):
                            continue

                        is_available = slot.get("available", not slot.get("isFull", True))
                        price = slot.get("price") or slot.get("fee")

                        slots.append({
                            "fulfillment_type": fulfillment_type,
                            "slot_date": slot_date,
                            "slot_start": start_dt,
                            "slot_end": end_dt,
                            "is_available": bool(is_available),
                            "price_nzd": float(price) if price else None,
                        })
            except Exception:
                logger.debug(
                    f"Foodstuffs slot fetch failed for {store.name} ({fulfillment_type})",
                    exc_info=True,
                )

        return slots


class NewWorldSlotScraper(FoodstuffsSlotScraper):
    chain = "new_world"
    site_url = "https://www.newworld.co.nz"


class PakNSaveSlotScraper(FoodstuffsSlotScraper):
    chain = "paknsave"
    site_url = "https://www.paknsave.co.nz"


SLOT_SCRAPERS: dict[str, type[SlotScraper]] = {
    "countdown": CountdownSlotScraper,
    "new_world": NewWorldSlotScraper,
    "paknsave": PakNSaveSlotScraper,
}


async def run_all_slot_scrapers() -> dict[str, int]:
    """Run slot scrapers for all chains. Returns {chain: slots_upserted}."""
    results = {}
    for chain, scraper_cls in SLOT_SCRAPERS.items():
        try:
            scraper = scraper_cls()
            count = await scraper.run()
            results[chain] = count
        except Exception:
            logger.exception(f"Slot scraper failed for {chain}")
            results[chain] = 0
    return results


__all__ = [
    "SlotScraper",
    "CountdownSlotScraper",
    "NewWorldSlotScraper",
    "PakNSaveSlotScraper",
    "SLOT_SCRAPERS",
    "run_all_slot_scrapers",
]
