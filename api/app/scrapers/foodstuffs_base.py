"""
Base scraper for Foodstuffs chains (New World, PakNSave) using their shared API infrastructure.
Both chains use identical API endpoints with only different domains and store IDs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, List, Optional

import httpx
from sqlalchemy import select

from app.db.models import IngestionRun, Store
from app.db.session import async_transaction, get_async_session
from app.scrapers.base import Scraper
from app.scrapers.api_auth_base import APIAuthBase
from app.services.normalizer import (
    clean_product_name,
    extract_size_from_text,
    normalize_brand,
    parse_structured_size,
)
from app.workers.retry import retry_with_backoff

logger = logging.getLogger(__name__)

# Concurrency controls
CATEGORY_CONCURRENCY = 3   # max concurrent category fetches per store
PERSIST_BATCH_SIZE = 200    # products per DB upsert batch
INTER_STORE_DELAY = 0.5     # seconds between stores


class FoodstuffsAPIScraper(Scraper, APIAuthBase):
    """
    Base scraper for Foodstuffs chains (New World, PakNSave).

    Both chains share the same API infrastructure with only different domains.
    Subclasses must define: chain, site_url, api_domain, api_url, default_store_id, store_data_file
    """

    # Subclasses must override these
    chain: str = None
    site_url: str = None
    api_domain: str = None
    api_url: str = None
    default_store_id: str = None
    store_data_file: str = None  # e.g., "newworld_stores.json"

    # Foodstuffs API categories: (category0NI, category1NI) as used in the
    # search filter.  These must match the *actual* API values (which changed
    # in late 2025 — run a facet probe if results drop to zero).
    categories = [
        # Fruit & Vegetables
        ("Fruit & Vegetables", "Fruit"),
        ("Fruit & Vegetables", "Vegetables"),
        ("Fruit & Vegetables", "Fresh Salad & Herbs"),
        # Meat, Poultry & Seafood
        ("Meat, Poultry & Seafood", "Beef"),
        ("Meat, Poultry & Seafood", "Chicken & Poultry"),
        ("Meat, Poultry & Seafood", "Pork & Ham"),
        ("Meat, Poultry & Seafood", "Lamb"),
        ("Meat, Poultry & Seafood", "Mince, Sausages & Meatballs"),
        ("Meat, Poultry & Seafood", "Deli Meats"),
        # Fridge, Deli & Eggs
        ("Fridge, Deli & Eggs", "Milk"),
        ("Fridge, Deli & Eggs", "Cheese"),
        ("Fridge, Deli & Eggs", "Yoghurt"),
        ("Fridge, Deli & Eggs", "Eggs"),
        ("Fridge, Deli & Eggs", "Butter & Margarine"),
        ("Fridge, Deli & Eggs", "Cream, Custard & Desserts"),
        ("Fridge, Deli & Eggs", "Deli Meats & Smoked Fish"),
        # Bakery
        ("Bakery", "Sliced & Packaged Bread"),
        ("Bakery", "In-Store Bakery"),
        ("Bakery", "Bagels, Crumpets & Pancakes"),
        ("Bakery", "Gluten Free, Low Carb & Keto"),
        # Pantry
        ("Pantry", "Canned Foods & Packets"),
        ("Pantry", "Pasta, Rice & Noodles"),
        ("Pantry", "Table Sauces, Dressings & Condiments"),
        ("Pantry", "Baking Supplies & Sugar"),
        ("Pantry", "Breakfast Cereals"),
        ("Pantry", "Oil & Vinegar"),
        ("Pantry", "Long Life & Dairy Free Milk"),
        ("Pantry", "Spices, Seasoning & Coatings"),
        ("Pantry", "Biscuits & Crackers"),
        ("Pantry", "Chips, Nuts & Snacks"),
        ("Pantry", "Chocolate, Sweets & Chewing Gum"),
        # Frozen
        ("Frozen", "Frozen Chips & Hash Browns"),
        ("Frozen", "Frozen Chicken & Meat"),
        ("Frozen", "Frozen Pizza & Ready Meals"),
        ("Frozen", "Frozen Fruit & Desserts"),
        ("Frozen", "Frozen Dumplings, Pies & Snacks"),
        ("Frozen", "Frozen Pastry & Bread"),
        # Hot & Cold Drinks
        ("Hot & Cold Drinks", "Water"),
        ("Hot & Cold Drinks", "Soft Drinks & Mixers"),
        ("Hot & Cold Drinks", "Juice & Smoothies"),
        ("Hot & Cold Drinks", "Coffee"),
        ("Hot & Cold Drinks", "Tea"),
        ("Hot & Cold Drinks", "Sports & Energy Drinks"),
        ("Hot & Cold Drinks", "Hot Chocolate & Milk Drinks"),
        # Snacks, Treats & Easy Meals
        ("Snacks, Treats & Easy Meals", "Chips, Nuts & Snacks"),
        ("Snacks, Treats & Easy Meals", "Chocolate, Sweets & Chewing Gum"),
        ("Snacks, Treats & Easy Meals", "Ready to Eat"),
        ("Snacks, Treats & Easy Meals", "Lunchbox Snacks"),
        ("Snacks, Treats & Easy Meals", "Easy Meals & Meal Kits"),
        # Health & Body
        ("Health & Body", "Tissues & Cotton Wool"),
        # Household & Cleaning
        ("Household & Cleaning", "Toilet Paper, Tissues & Paper Towels"),
        ("Household & Cleaning", "Food Wrap, Storage & Bags"),
        ("Household & Cleaning", "Garage & Outdoor"),
        ("Household & Cleaning", "Stationery & Entertainment"),
        # Baby & Toddler
        ("Baby & Toddler", "Baby Wipes"),
        # Pets
        ("Pets", "Dog"),
        ("Pets", "Cat"),
        # Beer, Wine & Cider
        ("Beer, Wine & Cider", "Beer"),
        ("Beer, Wine & Cider", "Red Wine"),
        ("Beer, Wine & Cider", "White Wine"),
        ("Beer, Wine & Cider", "Cider"),
        # Seasonal
        ("Easter", "Easter"),
    ]

    # Map Foodstuffs API category names → our canonical category/subcategory.
    # Keys are (level0, level1) from the API; values are (category, subcategory)
    # for our DB schema (matching CategoryFilter.tsx and CATEGORY_HIERARCHY).
    _CATEGORY_MAP: dict[tuple[str, str], tuple[str, str]] = {
        # Fruit & Vegetables (pass-through)
        ("Fruit & Vegetables", "Fruit"): ("Fruit & Vegetables", "Fruit"),
        ("Fruit & Vegetables", "Vegetables"): ("Fruit & Vegetables", "Vegetables"),
        ("Fruit & Vegetables", "Fresh Salad & Herbs"): ("Fruit & Vegetables", "Salad"),
        # Meat
        ("Meat, Poultry & Seafood", "Beef"): ("Meat & Seafood", "Beef & Veal"),
        ("Meat, Poultry & Seafood", "Chicken & Poultry"): ("Meat & Seafood", "Chicken"),
        ("Meat, Poultry & Seafood", "Pork & Ham"): ("Meat & Seafood", "Pork"),
        ("Meat, Poultry & Seafood", "Lamb"): ("Meat & Seafood", "Lamb"),
        ("Meat, Poultry & Seafood", "Mince, Sausages & Meatballs"): ("Meat & Seafood", "Mince & Patties"),
        ("Meat, Poultry & Seafood", "Deli Meats"): ("Meat & Seafood", "Deli & Cooked Meats"),
        # Fridge / Dairy
        ("Fridge, Deli & Eggs", "Milk"): ("Chilled, Dairy & Eggs", "Milk"),
        ("Fridge, Deli & Eggs", "Cheese"): ("Chilled, Dairy & Eggs", "Cheese"),
        ("Fridge, Deli & Eggs", "Yoghurt"): ("Chilled, Dairy & Eggs", "Yoghurt"),
        ("Fridge, Deli & Eggs", "Eggs"): ("Chilled, Dairy & Eggs", "Eggs"),
        ("Fridge, Deli & Eggs", "Butter & Margarine"): ("Chilled, Dairy & Eggs", "Butter & Margarine"),
        ("Fridge, Deli & Eggs", "Cream, Custard & Desserts"): ("Chilled, Dairy & Eggs", "Cream & Sour Cream"),
        ("Fridge, Deli & Eggs", "Deli Meats & Smoked Fish"): ("Chilled, Dairy & Eggs", "Deli & Cooked Meats"),
        # Bakery
        ("Bakery", "Sliced & Packaged Bread"): ("Bakery", "Bread"),
        ("Bakery", "In-Store Bakery"): ("Bakery", "Cakes & Muffins"),
        ("Bakery", "Bagels, Crumpets & Pancakes"): ("Bakery", "Rolls & Buns"),
        ("Bakery", "Gluten Free, Low Carb & Keto"): ("Bakery", "Bread"),
        # Pantry
        ("Pantry", "Canned Foods & Packets"): ("Pantry", "Canned Goods"),
        ("Pantry", "Pasta, Rice & Noodles"): ("Pantry", "Pasta, Rice & Noodles"),
        ("Pantry", "Table Sauces, Dressings & Condiments"): ("Pantry", "Sauces & Condiments"),
        ("Pantry", "Baking Supplies & Sugar"): ("Pantry", "Baking"),
        ("Pantry", "Breakfast Cereals"): ("Pantry", "Breakfast Cereals"),
        ("Pantry", "Oil & Vinegar"): ("Pantry", "Oil & Vinegar"),
        ("Pantry", "Long Life & Dairy Free Milk"): ("Chilled, Dairy & Eggs", "Milk"),
        ("Pantry", "Spices, Seasoning & Coatings"): ("Pantry", "Sauces & Condiments"),
        ("Pantry", "Biscuits & Crackers"): ("Snacks & Confectionery", "Biscuits"),
        ("Pantry", "Chips, Nuts & Snacks"): ("Snacks & Confectionery", "Chips & Crackers"),
        ("Pantry", "Chocolate, Sweets & Chewing Gum"): ("Snacks & Confectionery", "Chocolate"),
        # Frozen
        ("Frozen", "Frozen Chips & Hash Browns"): ("Frozen", "Frozen Chips & Wedges"),
        ("Frozen", "Frozen Chicken & Meat"): ("Frozen", "Frozen Meat & Seafood"),
        ("Frozen", "Frozen Pizza & Ready Meals"): ("Frozen", "Frozen Pizza"),
        ("Frozen", "Frozen Fruit & Desserts"): ("Frozen", "Ice Cream & Desserts"),
        ("Frozen", "Frozen Dumplings, Pies & Snacks"): ("Frozen", "Frozen Meals"),
        ("Frozen", "Frozen Pastry & Bread"): ("Frozen", "Frozen Meals"),
        # Drinks
        ("Hot & Cold Drinks", "Water"): ("Drinks", "Water"),
        ("Hot & Cold Drinks", "Soft Drinks & Mixers"): ("Drinks", "Soft Drinks"),
        ("Hot & Cold Drinks", "Juice & Smoothies"): ("Drinks", "Juice"),
        ("Hot & Cold Drinks", "Coffee"): ("Drinks", "Coffee"),
        ("Hot & Cold Drinks", "Tea"): ("Drinks", "Tea"),
        ("Hot & Cold Drinks", "Sports & Energy Drinks"): ("Drinks", "Energy & Sports Drinks"),
        ("Hot & Cold Drinks", "Hot Chocolate & Milk Drinks"): ("Drinks", "Coffee"),
        # Snacks
        ("Snacks, Treats & Easy Meals", "Chips, Nuts & Snacks"): ("Snacks & Confectionery", "Chips & Crackers"),
        ("Snacks, Treats & Easy Meals", "Chocolate, Sweets & Chewing Gum"): ("Snacks & Confectionery", "Chocolate"),
        ("Snacks, Treats & Easy Meals", "Ready to Eat"): ("Snacks & Confectionery", "Chips & Crackers"),
        ("Snacks, Treats & Easy Meals", "Lunchbox Snacks"): ("Snacks & Confectionery", "Biscuits"),
        ("Snacks, Treats & Easy Meals", "Easy Meals & Meal Kits"): ("Pantry", "Canned Goods"),
        # Health & Body
        ("Health & Body", "Tissues & Cotton Wool"): ("Health & Beauty", None),
        # Household
        ("Household & Cleaning", "Toilet Paper, Tissues & Paper Towels"): ("Household", "Toilet Paper & Tissues"),
        ("Household & Cleaning", "Food Wrap, Storage & Bags"): ("Household", "Cleaning"),
        ("Household & Cleaning", "Garage & Outdoor"): ("Household", "Cleaning"),
        ("Household & Cleaning", "Stationery & Entertainment"): ("Household", "Cleaning"),
        # Baby
        ("Baby & Toddler", "Baby Wipes"): ("Baby & Child", "Nappies"),
        # Pet
        ("Pets", "Dog"): ("Pet", "Dog Food"),
        ("Pets", "Cat"): ("Pet", "Cat Food"),
        # Beer, Wine & Cider (pass-through)
        ("Beer, Wine & Cider", "Beer"): ("Beer, Wine & Cider", None),
        ("Beer, Wine & Cider", "Red Wine"): ("Beer, Wine & Cider", None),
        ("Beer, Wine & Cider", "White Wine"): ("Beer, Wine & Cider", None),
        ("Beer, Wine & Cider", "Cider"): ("Beer, Wine & Cider", None),
        # Seasonal
        ("Easter", "Easter"): ("Snacks & Confectionery", "Chocolate"),
    }

    # Refresh token 5 minutes before expiry (token lasts 30 min / 1800s)
    TOKEN_TTL_SECONDS = 1800
    TOKEN_REFRESH_BUFFER_SECONDS = 300  # refresh 5 min early

    def __init__(self, scrape_all_stores: bool = True):
        Scraper.__init__(self)
        APIAuthBase.__init__(self)
        self.store_id: str = self.default_store_id
        self.scrape_all_stores = scrape_all_stores
        self.store_list = self._load_store_list() if scrape_all_stores else []
        self._token_obtained_at: float = 0
        self._http: Optional[httpx.AsyncClient] = None
        self._token_lock = asyncio.Lock()

    async def _load_store_list_from_db(self) -> List[dict]:
        """Load store API IDs for this chain from database (source of truth)."""
        stores: List[dict] = []

        try:
            async with get_async_session() as session:
                result = await session.execute(
                    select(Store.api_id, Store.name)
                    .where(Store.chain == self.chain)
                    .where(Store.api_id.is_not(None))
                )
                for api_id, name in result.all():
                    if not api_id:
                        continue
                    stores.append({"id": str(api_id), "name": name or str(api_id)})

        except Exception as e:
            logger.warning(f"Failed loading {self.chain} stores from DB, using fallback list: {e}")
            return []

        return stores

    def _load_store_list(self) -> List[dict]:
        """Load store list from JSON file."""
        try:
            current_dir = Path(__file__).parent
            data_file = current_dir.parent / "data" / self.store_data_file

            if not data_file.exists():
                logger.warning(f"Store list file not found: {data_file}")
                return []

            with open(data_file, 'r') as f:
                stores = json.load(f)

            logger.info(f"Loaded {len(stores)} {self.chain} stores from {data_file}")
            return stores
        except Exception as e:
            logger.error(f"Failed to load store list: {e}")
            return []

    async def _get_auth_token(self) -> Optional[str]:
        """Get authentication token.

        Strategy (in order):
        1. Direct HTTP call to /api/user/get-current-user (fast, no browser).
        2. Browser-based capture (fallback for if the direct endpoint changes).
        """
        # --- Fast path: direct HTTP token request ---
        token = await self._get_token_direct()
        if token:
            return token

        logger.warning(f"{self.chain}: direct token request failed, falling back to browser auth")

        # --- Slow path: browser-based capture ---
        return await self._get_auth_via_browser(
            capture_token=True,
            capture_cookies=True,
            headless=True,
            wait_time=10.0
        )

    async def _get_token_direct(self) -> Optional[str]:
        """Request a guest auth token directly via the site's Next.js API route."""
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
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.post(url, headers=headers, json={})
                resp.raise_for_status()
                data = resp.json()

                token = data.get("access_token")
                if not token:
                    logger.warning(f"{self.chain}: /api/user/get-current-user returned no access_token")
                    return None

                # Capture cookies from the response
                self.cookies = {name: value for name, value in resp.cookies.items()}
                logger.info(
                    f"{self.chain}: obtained auth token via direct HTTP "
                    f"({len(token)} chars, {len(self.cookies)} cookies)"
                )
                return token

        except Exception as e:
            logger.warning(f"{self.chain}: direct token request failed: {e}")
            return None

    def _get_http_client(self) -> httpx.AsyncClient:
        """Return a shared HTTP client, creating one if needed."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def _close_http_client(self) -> None:
        """Close the shared HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    async def _fetch_category(
        self,
        level0: str,
        level1: str,
        page: int = 0,
        hits_per_page: int = 50,
        store_id: Optional[str] = None,
    ) -> dict:
        """Fetch products for a specific category using the API."""
        sid = store_id or self.store_id
        domain = self.site_url.split("//")[-1].split("/")[0]

        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "origin": f"https://{domain}",
            "referer": f"https://{domain}/",
        }
        if self.auth_token:
            headers["authorization"] = f"Bearer {self.auth_token}"

        if self.cookies:
            cookie_string = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
            headers["cookie"] = cookie_string

        payload = {
            "algoliaQuery": {
                "attributesToHighlight": [],
                "attributesToRetrieve": [
                    "productID",
                    "Type",
                    "sponsored",
                    "category0NI",
                    "category1NI",
                    "category2NI"
                ],
                "facets": [
                    "brand",
                    "category2NI",
                    "onPromotion",
                    "productFacets",
                    "tobacco"
                ],
                "filters": f'stores:{sid} AND category0NI:"{level0}" AND category1NI:"{level1}"',
                "hitsPerPage": hits_per_page,
                "page": page,
            },
            "storeId": sid,
            "hitsPerPage": hits_per_page,
            "page": page,
            "sortOrder": "NI_POPULARITY_ASC",
            "tobaccoQuery": False,
        }

        client = self._get_http_client()
        response = await client.post(self.api_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    async def _probe_cookie_only_access(self) -> bool:
        """Check whether API access works without bearer token using session cookies only."""
        if not self.categories:
            return False

        level0, level1 = self.categories[0]
        try:
            await self._fetch_category(level0, level1, page=0, hits_per_page=1)
            return True
        except Exception as e:
            logger.warning(f"Cookie-only API probe failed for {self.chain}: {e}")
            return False

    def _parse_product(
        self,
        product_data: dict,
        level0: Optional[str] = None,
        level1: Optional[str] = None,
    ) -> dict:
        """Parse a product from API response into our standard format.

        *level0* and *level1* are the API category filter values used to
        fetch this product (e.g. ``"Fridge, Deli & Eggs"``, ``"Milk"``).
        They are mapped to our canonical category/subcategory via
        ``_CATEGORY_MAP``.
        """
        product_id = product_data.get("productId", "")
        brand = product_data.get("brand", "")
        name = product_data.get("name", "")
        display_name = product_data.get("displayName", "")

        # Full product name
        full_name = f"{brand} {name} {display_name}".strip()

        # Price (in cents, convert to dollars)
        price_cents = product_data.get("singlePrice", {}).get("price", 0)
        price = price_cents / 100

        # Promotions
        promo_price = None
        promo_text = None
        promo_ends_at = None
        is_member_only = False

        promotions = product_data.get("promotions", [])
        if promotions:
            best_promo = next(
                (p for p in promotions if p.get("bestPromotion")),
                promotions[0] if promotions else None
            )

            if best_promo:
                reward_value = best_promo.get("rewardValue")
                if reward_value and reward_value < price_cents:
                    promo_price = reward_value / 100

                reward_type = best_promo.get("rewardType", "")
                decal = best_promo.get("decal", "")
                if decal:
                    promo_text = decal[:255]
                elif reward_type == "NEW_PRICE":
                    promo_text = "Special Price"

                is_member_only = best_promo.get("cardDependencyFlag", False)

        # Image URL
        product_id_prefix = product_id.split("-")[0] if "-" in product_id else product_id
        image_url = f"https://a.fsimg.co.nz/product/retail/fan/image/400x400/{product_id_prefix}.png"

        # Product URL
        domain = self.site_url.split("//")[-1].split("/")[0]
        slug = full_name.lower().replace(" ", "-").replace("'", "")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        url = f"https://{domain}/shop/product/{product_id.lower().replace('-', '_')}?name={slug}"

        # Map API categories to our canonical category/subcategory
        category: Optional[str] = None
        subcategory: Optional[str] = None
        if level0 and level1:
            mapped = self._CATEGORY_MAP.get((level0, level1))
            if mapped:
                category, subcategory = mapped
            else:
                # Unmapped — store the API name as department for debugging
                category = level0
                subcategory = level1

        # Extract size from displayName (not the raw displayName — just the size portion)
        raw_display = product_data.get("displayName", "") or ""
        size_value = extract_size_from_text(raw_display) or extract_size_from_text(full_name)

        # Parse structured size fields for numeric matching
        structured = parse_structured_size(size_value or full_name)

        # Extract unit pricing (cupPrice/cupMeasure from Foodstuffs API)
        cup_price = product_data.get("cupPrice")
        cup_measure = product_data.get("cupMeasure", "")
        unit_price = None
        unit_measure = None
        if cup_price:
            try:
                unit_price = float(cup_price) / 100 if cup_price > 1 else float(cup_price)
            except (ValueError, TypeError):
                pass
            unit_measure = cup_measure or None

        return self.build_product_dict(
            source_id=product_id,
            name=full_name,
            price_nzd=price,
            promo_price_nzd=promo_price,
            promo_text=promo_text,
            promo_ends_at=promo_ends_at,
            is_member_only=is_member_only,
            url=url,
            image_url=image_url,
            brand=brand or None,
            category=category,
            department=level0,
            subcategory=subcategory,
            size=size_value or None,
            unit_price=unit_price,
            unit_measure=unit_measure,
            volume_ml=structured.volume_ml,
            weight_g=structured.weight_g,
            pack_count=structured.pack_count,
            normalized_name=clean_product_name(full_name, brand),
            normalized_brand=normalize_brand(brand) if brand else None,
        )

    async def fetch_catalog_pages(self) -> List[str]:
        """Not used for API-based scraper - implemented for base class compatibility."""
        return []

    async def parse_products(self, payload: str) -> List[dict]:
        """Not used for API-based scraper - implemented for base class compatibility."""
        return []

    _sweep_per_store = True

    async def run(self) -> IngestionRun:
        """Run the scraper and persist data to database."""
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
            products = await self.scrape()
            total_items = len(products)
            changed_items = 0
            failed_items = 0

            # Track store UUIDs we actually wrote to, for per-store sweep
            seen_store_ids: set = set()

            for product_data in products:
                try:
                    async with async_transaction() as session:
                        store_api_id = product_data.get('store_id')
                        if store_api_id:
                            result = await session.execute(
                                select(Store).where(
                                    Store.chain == self.chain,
                                    Store.api_id == store_api_id
                                )
                            )
                            store = result.scalar_one_or_none()

                            if store:
                                seen_store_ids.add(store.id)
                                changed = await self._upsert_product_and_prices(
                                    session, product_data, [store]
                                )
                                if changed:
                                    changed_items += 1
                            else:
                                logger.debug(f"Store not found in DB for api_id={store_api_id}, skipping price")
                                failed_items += 1
                        else:
                            logger.warning(f"Product {product_data.get('name')} has no store_id")
                            failed_items += 1
                except Exception as e:
                    logger.error(f"Failed to persist product {product_data.get('name')}: {e}")
                    failed_items += 1

            # Sweep stale promos for each store we scraped
            if self._run_started_at and seen_store_ids:
                try:
                    from app.services.freshness import sweep_store_promos

                    async with async_transaction() as session:
                        for sid in seen_store_ids:
                            await sweep_store_promos(session, sid, self._run_started_at)
                except Exception as e:
                    logger.warning(f"Per-store promo sweep failed for chain={self.chain}: {e}")

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
                f"{changed_items} changed, {failed_items} failed"
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

    def _token_age_seconds(self) -> float:
        """How many seconds since the current token was obtained."""
        if self._token_obtained_at == 0:
            return float("inf")
        return time.monotonic() - self._token_obtained_at

    def _token_needs_refresh(self) -> bool:
        """True if the token is close to expiry and should be refreshed."""
        return self._token_age_seconds() >= (self.TOKEN_TTL_SECONDS - self.TOKEN_REFRESH_BUFFER_SECONDS)

    async def _refresh_token_if_needed(self) -> bool:
        """Refresh the auth token if it's close to expiry. Returns True if token is valid.

        Uses a lock to prevent concurrent refresh attempts from racing.
        """
        if not self._token_needs_refresh():
            return True

        async with self._token_lock:
            # Re-check after acquiring lock (another coroutine may have refreshed)
            if not self._token_needs_refresh():
                return True

            age = self._token_age_seconds()
            logger.info(f"{self.chain}: token is {age:.0f}s old (limit {self.TOKEN_TTL_SECONDS}s), refreshing...")
            self.auth_token = await self._get_auth_token()
            if self.auth_token:
                self._token_obtained_at = time.monotonic()
                logger.info(f"{self.chain}: token refreshed successfully")
                return True

            logger.error(f"{self.chain}: token refresh failed")
            return False

    async def _validate_auth(self) -> bool:
        """Validate that the auth token is still valid by making a lightweight API call."""
        if not self.categories:
            return False
        level0, level1 = self.categories[0]
        try:
            response = await self._fetch_category(level0, level1, page=0, hits_per_page=1)
            count = response.get("totalProducts", 0)
            logger.info(f"{self.chain}: auth validation passed ({count} products in {level1})")
            return True
        except Exception as e:
            logger.warning(f"{self.chain}: auth validation failed: {e}")
            return False

    async def _ensure_auth(self) -> bool:
        """Ensure we have a valid auth token, obtaining one if needed."""
        if not self.auth_token:
            self.auth_token = await self._get_auth_token()
            if not self.auth_token:
                logger.error(
                    f"Unable to authenticate {self.chain}: "
                    "both direct HTTP and browser token capture failed"
                )
                return False
            self._token_obtained_at = time.monotonic()

        if not await self._validate_auth():
            logger.warning(f"{self.chain}: stale token detected, refreshing...")
            self.auth_token = await self._get_auth_token()
            if not self.auth_token or not await self._validate_auth():
                logger.error(f"{self.chain}: auth validation failed after refresh")
                return False
            self._token_obtained_at = time.monotonic()

        return True

    def _resolve_stores(self) -> List[dict]:
        """Synchronous helper to determine the store list to scrape."""
        if not self.scrape_all_stores:
            return [{"id": self.default_store_id, "name": "Default Store"}]
        if self.store_list:
            return self.store_list
        return [{"id": self.default_store_id, "name": "Default Store"}]

    async def _resolve_stores_async(self) -> List[dict]:
        """Determine the store list, preferring DB, falling back to JSON."""
        if not self.scrape_all_stores:
            logger.info("Scraping single store (default)")
            return [{"id": self.default_store_id, "name": "Default Store"}]

        db_stores = await self._load_store_list_from_db()
        if db_stores:
            logger.info(f"Scraping all {len(db_stores)} {self.chain} stores from database")
            return db_stores
        if self.store_list:
            logger.info(f"Scraping all {len(self.store_list)} {self.chain} stores from JSON fallback")
            return self.store_list

        logger.warning(f"No {self.chain} store list found in DB/JSON; scraping default store only")
        return [{"id": self.default_store_id, "name": "Default Store"}]

    async def _scrape_category(
        self,
        sem: asyncio.Semaphore,
        level0: str,
        level1: str,
        store_id: str,
    ) -> List[dict]:
        """Fetch all pages for a single category, gated by semaphore."""
        async with sem:
            products: List[dict] = []
            try:
                response = await retry_with_backoff(
                    lambda: self._fetch_category(level0, level1, page=0, store_id=store_id),
                    max_retries=3,
                    base_delay=5.0,
                    label=f"{self.chain} {level0}/{level1}",
                )
                products_data = response.get("products", [])
                total_products = response.get("totalProducts", len(products_data))

                for pd in products_data:
                    try:
                        products.append(self._parse_product(pd, level0, level1))
                    except Exception as e:
                        logger.error(f"Error parsing product: {e}")

                # Paginate remaining pages (sequential within this category)
                hits_per_page = 50
                total_pages = (total_products + hits_per_page - 1) // hits_per_page

                for page_num in range(1, total_pages):
                    response = await retry_with_backoff(
                        lambda _p=page_num: self._fetch_category(
                            level0, level1, page=_p, store_id=store_id
                        ),
                        max_retries=3,
                        base_delay=5.0,
                        label=f"{self.chain} {level1} p{page_num + 1}",
                    )
                    for pd in response.get("products", []):
                        try:
                            products.append(self._parse_product(pd, level0, level1))
                        except Exception as e:
                            logger.error(f"Error parsing product: {e}")
                    await asyncio.sleep(0.3)

            except Exception as e:
                logger.error(f"Error scraping category {level1}: {e}")

            await asyncio.sleep(0.2)
            return products

    async def _scrape_by_store(self) -> AsyncIterator[tuple[str, List[dict]]]:
        """Async generator that yields (store_api_id, products) per store.

        Categories within each store are fetched concurrently (up to
        CATEGORY_CONCURRENCY at a time).
        """
        if not await self._ensure_auth():
            return

        stores_to_scrape = await self._resolve_stores_async()
        sem = asyncio.Semaphore(CATEGORY_CONCURRENCY)

        for store_idx, store in enumerate(stores_to_scrape, 1):
            store_id = store["id"]
            store_name = store.get("name", store_id)

            if not await self._refresh_token_if_needed():
                logger.error(f"{self.chain}: cannot continue without valid token, stopping at store {store_idx}")
                break

            logger.info(f"[{store_idx}/{len(stores_to_scrape)}] Scraping store: {store_name}")

            # Fetch all categories concurrently for this store
            tasks = [
                self._scrape_category(sem, l0, l1, store_id)
                for l0, l1 in self.categories
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            store_products: List[dict] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Category task failed for store {store_name}: {result}")
                    continue
                for p in result:
                    p["store_id"] = store_id
                    p["store_name"] = store_name
                    store_products.append(p)

            logger.info(f"  Store {store_name}: {len(store_products)} products")
            yield store_id, store_products

            if store_idx < len(stores_to_scrape):
                await asyncio.sleep(INTER_STORE_DELAY)

    async def scrape(self) -> List[dict]:
        """Scrape all products (backward-compatible flat list).

        For production use, prefer run() which streams per-store and
        persists in batches.
        """
        all_products: List[dict] = []
        async for _store_id, products in self._scrape_by_store():
            all_products.extend(products)
        logger.info(f"Successfully scraped {len(all_products)} products from {self.chain}")
        return all_products

    async def run(self) -> IngestionRun:
        """Run the scraper with batch persistence per store."""
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
            # Pre-load store map once (api_id -> Store)
            async with async_transaction() as session:
                result = await session.execute(
                    select(Store).where(Store.chain == self.chain)
                )
                store_map = {s.api_id: s for s in result.scalars().all()}

            total_items = 0
            changed_items = 0
            failed_items = 0
            seen_store_ids: set = set()

            async for store_api_id, products in self._scrape_by_store():
                store = store_map.get(store_api_id)
                if not store:
                    logger.debug(f"Store not found in DB for api_id={store_api_id}, skipping")
                    failed_items += len(products)
                    continue

                seen_store_ids.add(store.id)
                total_items += len(products)

                # Batch upsert (same pattern as Countdown's _persist_per_store)
                for batch_start in range(0, len(products), PERSIST_BATCH_SIZE):
                    batch = products[batch_start: batch_start + PERSIST_BATCH_SIZE]
                    try:
                        async with async_transaction() as session:
                            batch_changed = await self._upsert_products_batch(
                                session, batch, [store]
                            )
                        changed_items += batch_changed
                    except Exception as e:
                        logger.error(f"Failed batch for store {store.name}: {e}")
                        failed_items += len(batch)

            # Sweep stale promos for each store we scraped
            if self._run_started_at and seen_store_ids:
                try:
                    from app.services.freshness import sweep_store_promos

                    async with async_transaction() as session:
                        for sid in seen_store_ids:
                            await sweep_store_promos(session, sid, self._run_started_at)
                except Exception as e:
                    logger.warning(f"Per-store promo sweep failed for chain={self.chain}: {e}")

            failure_rate = failed_items / total_items if total_items > 0 else 0.0
            status = "completed_with_errors" if failure_rate > 0.2 else "completed"

            async with async_transaction() as session:
                result = await session.execute(
                    select(IngestionRun).where(IngestionRun.id == run.id)
                )
                run = result.scalar_one()
                run.status = status
                run.finished_at = datetime.utcnow()
                run.items_total = total_items
                run.items_changed = changed_items
                run.items_failed = failed_items

            logger.info(
                f"Scraper completed: {total_items} items, "
                f"{changed_items} changed, {failed_items} failed"
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
        finally:
            await self._close_http_client()


__all__ = ["FoodstuffsAPIScraper"]
