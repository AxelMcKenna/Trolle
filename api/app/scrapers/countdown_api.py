"""
Countdown API-based scraper using Woolworths NZ API.
Much faster and more reliable than HTML scraping.

Supports per-store pricing via the ``storeId`` query parameter.
Woolworths NZ introduced localised pricing in August 2024; prices now
differ between North Island and South Island (and sometimes per-store).

Note: Countdown NZ rebranded to Woolworths NZ (October 2023).
countdown.co.nz still redirects, but the live site and API are at woolworths.co.nz.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

import httpx
from sqlalchemy import select

from app.db.models import IngestionRun, Store
from app.db.session import async_transaction
from app.scrapers.base import Scraper
from app.services.category_mapper import classify_product

logger = logging.getLogger(__name__)


class CountdownAPIScraper(Scraper):
    """API-based scraper for Woolworths NZ (formerly Countdown).

    Scrapes per-store prices for online-capable stores (those whose
    product search API returns real results when given a ``storeId``
    parameter).  Remaining stores receive fallback national pricing
    from a default (no ``storeId``) scrape.
    """

    chain = "countdown"
    site_url = "https://www.woolworths.co.nz"
    api_url = "https://www.woolworths.co.nz/api/v1/products"
    store_data_file = "countdown_stores.json"

    # Per-store promo sweeping for online stores
    _sweep_per_store = True

    # Broad grocery search terms covering all departments
    search_terms = [
        # Fruit & Veg
        "apples", "bananas", "oranges", "tomatoes", "potatoes", "lettuce", "onions", "carrots",
        # Meat & Seafood
        "chicken", "beef", "lamb", "pork", "mince", "sausages", "salmon", "fish",
        # Dairy & Eggs
        "milk", "cheese", "yoghurt", "eggs", "butter", "cream",
        # Bakery
        "bread", "rolls", "wraps",
        # Pantry
        "rice", "pasta", "cereal", "canned", "soup", "sauce", "oil", "flour", "sugar", "spreads",
        # Frozen
        "frozen vegetables", "ice cream", "frozen pizza", "frozen chips",
        # Snacks & Drinks
        "chips", "chocolate", "biscuits", "nuts",
        "water", "juice", "soft drink", "coffee", "tea",
        # Household & Other
        "cleaning", "laundry", "toilet paper", "soap", "shampoo",
        "nappies", "baby food",
        "dog food", "cat food",
    ]

    def __init__(self):
        Scraper.__init__(self)
        self.cookies: dict = {}
        self._online_store_ids: Optional[set[str]] = None

    # ------------------------------------------------------------------
    # Store helpers
    # ------------------------------------------------------------------

    def _load_store_list(self) -> List[dict]:
        """Load store list from countdown_stores.json."""
        data_file = Path(__file__).parent.parent / "data" / self.store_data_file
        if not data_file.exists():
            logger.warning(f"Store list file not found: {data_file}")
            return []
        with open(data_file, "r") as f:
            stores = json.load(f)
        logger.info(f"Loaded {len(stores)} {self.chain} stores from {data_file}")
        return stores

    async def _load_online_store_ids(self) -> set[str]:
        """Probe the API to discover which store IDs return real products.

        A store is considered "online-capable" if a search for ``milk``
        with its ``storeId`` returns at least one item with a valid SKU.
        Results are cached for the scraper's lifetime.
        """
        if self._online_store_ids is not None:
            return self._online_store_ids

        all_stores = self._load_store_list()
        online: set[str] = set()

        for store in all_stores:
            sid = store.get("id", "")
            if not sid:
                continue
            try:
                data = await self._fetch_search("milk", page=1, size=3, store_id=sid)
                items = data.get("products", {}).get("items", [])
                real_items = [i for i in items if i.get("sku")]
                if real_items:
                    online.add(sid)
            except Exception:
                pass
            await asyncio.sleep(0.15)

        logger.info(
            f"Discovered {len(online)}/{len(all_stores)} online-capable stores"
        )
        self._online_store_ids = online
        return online

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get_cookies_direct(self) -> dict:
        """Capture server-set session cookies via a plain HTTP GET (no browser, no JS)."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                self.site_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-NZ,en;q=0.9",
                },
            )
            cookies = dict(resp.cookies)
            logger.info(f"Captured {len(cookies)} cookies via HTTP (status={resp.status_code})")
            return cookies

    async def _fetch_search(
        self,
        term: str,
        page: int = 1,
        size: int = 120,
        store_id: Optional[str] = None,
    ) -> dict:
        """Fetch products via search API, optionally scoped to a store."""
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-NZ",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "referer": f"https://www.woolworths.co.nz/shop/search?search={quote(term)}",
            "x-requested-with": "OnlineShopping.WebApp",
            "cache-control": "no-cache",
            "pragma": "no-cache",
        }

        if self.cookies:
            cookie_string = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
            headers["cookie"] = cookie_string

        url = (
            f"{self.api_url}?"
            f"target=search&"
            f"search={quote(term)}&"
            f"page={page}&"
            f"size={size}&"
            f"inStockProductsOnly=false"
        )
        if store_id:
            url += f"&storeId={store_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_product(self, product_data: dict) -> dict:
        """Parse a product from API response into our standard format."""
        sku = product_data.get("sku") or ""
        name = product_data.get("name") or ""
        brand = product_data.get("brand") or ""
        variety = product_data.get("variety") or ""

        full_name = f"{brand} {variety} {name}".strip()

        # Price info
        price_info = product_data.get("price", {})
        price = price_info.get("originalPrice", 0)
        sale_price = price_info.get("salePrice")
        is_special = price_info.get("isSpecial", False)

        promo_price = None
        promo_text = None
        if is_special and sale_price and sale_price < price:
            promo_price = sale_price
            save_price = price_info.get("savePrice", 0)
            if save_price:
                promo_text = f"Save ${save_price:.2f}"[:255]

        is_member_only = price_info.get("isClubPrice", False)

        images = product_data.get("images", {})
        image_url = images.get("big") or images.get("small")

        slug = product_data.get("slug", "")
        url = f"https://www.woolworths.co.nz/shop/productdetails?stockcode={sku}&name={slug}" if slug else None

        departments = product_data.get("departments") or []
        department = None
        if departments:
            department = departments[0].get("name") if departments else None

        # Classify into our canonical category/subcategory
        category, subcategory = classify_product(department, full_name)

        size_info = product_data.get("size", {})
        size_value = size_info.get("volumeSize", "") if size_info else ""

        unit_price = None
        unit_measure = None
        avg_qty_price = price_info.get("averageQuantityPrice")
        avg_qty_units = price_info.get("averageQuantityUnits", "")
        if avg_qty_price:
            unit_price = avg_qty_price
            unit_measure = avg_qty_units or None

        return self.build_product_dict(
            source_id=sku,
            name=full_name,
            price_nzd=price,
            promo_price_nzd=promo_price,
            promo_text=promo_text,
            promo_ends_at=None,
            is_member_only=is_member_only,
            url=url,
            image_url=image_url,
            brand=brand or None,
            category=category,
            department=department,
            subcategory=subcategory,
            size=size_value or None,
            unit_price=unit_price,
            unit_measure=unit_measure,
        )

    async def fetch_catalog_pages(self) -> List[str]:
        """Not used for API-based scraper."""
        return []

    async def parse_products(self, payload: str) -> List[dict]:
        """Not used for API-based scraper."""
        return []

    async def scrape(self) -> List[dict]:
        """Public scrape method (no store context, national pricing).

        Used by tests and as a quick standalone run.  For full per-store
        scraping use :meth:`run`.
        """
        if not await self._ensure_api_access():
            return []
        return await self._scrape_search_terms(store_id=None)

    # ------------------------------------------------------------------
    # Core scrape logic
    # ------------------------------------------------------------------

    async def _ensure_api_access(self) -> bool:
        """Establish API access (cookieless or with session cookies).

        Returns True if the API is reachable, False otherwise.
        """
        self.cookies = {}
        try:
            probe = await self._fetch_search("milk", page=1, size=5)
            probe_items = probe.get("products", {}).get("items", [])
        except Exception as e:
            logger.info(f"Cookieless probe failed ({e}) — will try HTTP cookie grab")
            probe_items = []

        if probe_items:
            logger.info(f"Cookieless access works ({len(probe_items)} items)")
            return True

        logger.info("Cookieless probe returned no items — fetching session cookies via HTTP")
        self.cookies = await self._get_cookies_direct()

        try:
            probe = await self._fetch_search("milk", page=1, size=5)
            probe_items = probe.get("products", {}).get("items", [])
        except Exception as e:
            logger.warning(f"Cookie probe also failed ({e}) — aborting scrape")
            return False

        if not probe_items:
            logger.warning("HTTP cookie auth returned no items — skipping scrape")
            return False

        logger.info(f"Cookie auth succeeded ({len(probe_items)} probe items)")
        return True

    async def _scrape_search_terms(
        self, store_id: Optional[str] = None
    ) -> List[dict]:
        """Run the full search-term sweep, returning parsed product dicts.

        If *store_id* is provided, each API call includes ``&storeId=…``
        and products are tagged with ``store_id``.
        """
        seen_skus: set[str] = set()
        all_products: List[dict] = []

        store_label = f" [store {store_id}]" if store_id else ""

        for term in self.search_terms:
            logger.info(f"Searching{store_label}: '{term}'")
            page_num = 1

            while True:
                try:
                    response = await self._fetch_search(
                        term, page=page_num, store_id=store_id
                    )
                    items = response.get("products", {}).get("items", [])

                    if not items:
                        break

                    new_count = 0
                    for item_data in items:
                        try:
                            sku = str(item_data.get("sku") or "")
                            if not sku or sku in seen_skus:
                                continue
                            seen_skus.add(sku)
                            product = self._parse_product(item_data)
                            if store_id:
                                product["store_id"] = store_id
                            all_products.append(product)
                            new_count += 1
                        except Exception as e:
                            logger.debug(f"Error parsing product: {e}")

                    logger.info(
                        f"  '{term}' page {page_num}{store_label}: "
                        f"{len(items)} items, {new_count} new"
                    )

                    if len(items) < 120:
                        break

                    page_num += 1
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"Error searching '{term}' page {page_num}{store_label}: {e}")
                    break

            await asyncio.sleep(1)

        logger.info(
            f"Scraped{store_label} {len(all_products)} unique products "
            f"from {len(seen_skus)} SKUs across {len(self.search_terms)} search terms"
        )
        return all_products

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def _persist_per_store(
        self,
        products: List[dict],
        store: Store,
    ) -> tuple[int, int]:
        """Upsert products for a single store. Returns (changed, failed)."""
        changed_items = 0
        failed_items = 0
        BATCH = 200

        for batch_start in range(0, len(products), BATCH):
            batch = products[batch_start: batch_start + BATCH]
            try:
                async with async_transaction() as session:
                    batch_changed = await self._upsert_products_batch(
                        session, batch, [store]
                    )
                changed_items += batch_changed
            except Exception as e:
                logger.error(f"Failed batch for store {store.name}: {e}")
                failed_items += len(batch)

        return changed_items, failed_items

    async def _persist_fallback(
        self,
        products: List[dict],
        stores: List[Store],
    ) -> tuple[int, int]:
        """Broadcast default prices to non-online stores. Returns (changed, failed)."""
        changed_items = 0
        failed_items = 0
        BATCH = 200

        for batch_start in range(0, len(products), BATCH):
            batch = products[batch_start: batch_start + BATCH]
            batch_num = batch_start // BATCH + 1
            total_batches = (len(products) + BATCH - 1) // BATCH
            logger.info(
                f"Fallback upsert batch {batch_num}/{total_batches} "
                f"({len(batch)} products x {len(stores)} stores)"
            )
            try:
                async with async_transaction() as session:
                    batch_changed = await self._upsert_products_batch(
                        session, batch, stores
                    )
                changed_items += batch_changed
            except Exception as e:
                logger.error(f"Failed fallback batch {batch_num}: {e}")
                failed_items += len(batch)

        return changed_items, failed_items

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self) -> IngestionRun:
        """Run the scraper with per-store pricing for online stores
        and fallback national pricing for the rest."""
        self._run_started_at = datetime.utcnow()

        run = IngestionRun(
            chain=self.chain,
            status="running",
            started_at=self._run_started_at,
        )

        async with async_transaction() as session:
            session.add(run)
            await session.flush()

        try:
            # Establish API access
            if not await self._ensure_api_access():
                raise RuntimeError("Could not establish API access")

            # Discover online-capable stores
            online_ids = await self._load_online_store_ids()

            # Load all DB stores for this chain, partitioned by online capability
            async with async_transaction() as session:
                result = await session.execute(
                    select(Store).where(Store.chain == self.chain)
                )
                all_stores = result.scalars().all()

            online_stores = [s for s in all_stores if s.api_id in online_ids]
            fallback_stores = [s for s in all_stores if s.api_id not in online_ids]

            logger.info(
                f"Store split: {len(online_stores)} online, "
                f"{len(fallback_stores)} fallback (total {len(all_stores)})"
            )

            total_items = 0
            changed_items = 0
            failed_items = 0
            seen_store_uuids: set = set()

            # Phase 1: Per-store scraping for online stores
            for idx, store in enumerate(online_stores, 1):
                logger.info(
                    f"[{idx}/{len(online_stores)}] Scraping store: "
                    f"{store.name} (api_id={store.api_id})"
                )
                products = await self._scrape_search_terms(store_id=store.api_id)
                total_items += len(products)

                if products:
                    changed, failed = await self._persist_per_store(products, store)
                    changed_items += changed
                    failed_items += failed
                    seen_store_uuids.add(store.id)

                # Per-store promo sweep
                if self._run_started_at and store.id in seen_store_uuids:
                    try:
                        from app.services.freshness import sweep_store_promos

                        async with async_transaction() as session:
                            await sweep_store_promos(
                                session, store.id, self._run_started_at
                            )
                    except Exception as e:
                        logger.warning(
                            f"Per-store promo sweep failed for {store.name}: {e}"
                        )

                # Delay between stores
                if idx < len(online_stores):
                    await asyncio.sleep(2)

            # Phase 2: Fallback scrape for non-online stores
            if fallback_stores:
                logger.info(
                    f"Running fallback scrape for {len(fallback_stores)} "
                    f"non-online stores"
                )
                fallback_products = await self._scrape_search_terms(store_id=None)
                total_items += len(fallback_products)

                if fallback_products:
                    changed, failed = await self._persist_fallback(
                        fallback_products, fallback_stores
                    )
                    changed_items += changed
                    failed_items += failed

                # Chain-wide promo sweep for fallback stores only
                if self._run_started_at:
                    try:
                        async with async_transaction() as session:
                            from sqlalchemy import update
                            from app.db.models import Price
                            fallback_store_ids = [s.id for s in fallback_stores]
                            stmt = (
                                update(Price)
                                .where(
                                    Price.store_id.in_(fallback_store_ids),
                                    Price.last_seen_at < self._run_started_at,
                                    Price.promo_price_nzd.is_not(None),
                                )
                                .values(
                                    promo_price_nzd=None,
                                    promo_text=None,
                                    promo_ends_at=None,
                                )
                            )
                            await session.execute(stmt)
                    except Exception as e:
                        logger.warning(f"Fallback promo sweep failed: {e}")

            # Update ingestion run
            async with async_transaction() as session:
                result = await session.execute(
                    select(IngestionRun).where(IngestionRun.id == run.id)
                )
                run = result.scalar_one()
                run.status = "completed"
                run.finished_at = datetime.utcnow()
                run.items_total = total_items
                run.items_changed = changed_items
                run.items_failed = failed_items

            logger.info(
                f"Scraper completed: {total_items} items, "
                f"{changed_items} changed, {failed_items} failed "
                f"({len(online_stores)} online + {len(fallback_stores)} fallback stores)"
            )
            return run

        except Exception as e:
            logger.error(f"Scraper failed: {e}")
            async with async_transaction() as session:
                result = await session.execute(
                    select(IngestionRun).where(IngestionRun.id == run.id)
                )
                run = result.scalar_one()
                run.status = "failed"
                run.finished_at = datetime.utcnow()
            raise


__all__ = ["CountdownAPIScraper"]
