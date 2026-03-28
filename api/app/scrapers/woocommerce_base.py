"""WooCommerce Store API scraper base class.

Fetches products from any WooCommerce site using the public
``wp-json/wc/store/v1/products`` endpoint (no authentication required).

Subclasses only need to set ``chain``, ``site_url``, and optionally
override category mapping or filtering logic.
"""
from __future__ import annotations

import json
import logging
import re
from typing import AsyncIterator, List, Optional

import httpx

from app.scrapers.base import Scraper
from app.services.category_mapper import classify_product
from app.services.normalizer import (
    clean_product_name,
    normalize_brand,
    parse_structured_size,
)

logger = logging.getLogger(__name__)

# WooCommerce Store API returns max 100 per page
_MAX_PER_PAGE = 100


class WooCommerceScraper(Scraper):
    """Base scraper for WooCommerce sites using the public Store API."""

    chain: str
    site_url: str  # e.g. "https://www.madbutcher.co.nz"

    # Subclasses can override to filter out non-meat categories
    exclude_categories: set[str] = set()

    # Department override for classify_product — butcher products are
    # almost always meat, so we default to "Meat & Poultry".
    default_department: str = "Meat & Poultry"

    # WooCommerce category slug → our department mapping
    category_department_map: dict[str, str] = {
        "beef": "Meat & Poultry",
        "lamb": "Meat & Poultry",
        "pork": "Meat & Poultry",
        "chicken": "Meat & Poultry",
        "poultry": "Meat & Poultry",
        "game": "Meat & Poultry",
        "smallgoods": "Meat & Poultry",
        "sausages": "Meat & Poultry",
        "mince": "Meat & Poultry",
        "seafood": "Fish & Seafood",
        "fish": "Fish & Seafood",
        "frozen": "Frozen",
        "freezer": "Frozen",
        "pantry": "Pantry",
        "groceries": "Pantry",
        "bbq": "Meat & Poultry",
        "specials": None,  # Use other categories or default
        "meat-packs": "Meat & Poultry",
    }

    def __init__(self) -> None:
        super().__init__()
        self._http: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def _close_http_client(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    @property
    def _api_url(self) -> str:
        return f"{self.site_url}/wp-json/wc/store/v1/products"

    async def _fetch_page(self, page: int = 1) -> list[dict]:
        """Fetch a page of products from the WooCommerce Store API."""
        client = self._get_http_client()
        resp = await client.get(
            self._api_url,
            params={"per_page": _MAX_PER_PAGE, "page": page},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def _fetch_all_products(self) -> list[dict]:
        """Fetch all products across all pages."""
        all_products: list[dict] = []
        page = 1

        while True:
            products = await self._fetch_page(page)
            if not products:
                break
            all_products.extend(products)
            logger.info(
                f"[{self.chain}] Fetched page {page}: {len(products)} products"
            )
            # If we got fewer than max, we've reached the last page
            if len(products) < _MAX_PER_PAGE:
                break
            page += 1

        logger.info(
            f"[{self.chain}] Total products fetched: {len(all_products)}"
        )
        return all_products

    def _get_department(self, categories: list[dict]) -> Optional[str]:
        """Map WooCommerce categories to our department."""
        for cat in categories:
            slug = cat.get("slug", "").lower()
            if slug in self.category_department_map:
                dept = self.category_department_map[slug]
                if dept is not None:
                    return dept
        return self.default_department

    def _get_wc_category_name(self, categories: list[dict]) -> Optional[str]:
        """Get the most specific WooCommerce category name."""
        # Prefer non-"specials" categories
        for cat in categories:
            slug = cat.get("slug", "").lower()
            if slug not in ("specials", "weekly-specials", "uncategorized"):
                return cat.get("name")
        if categories:
            return categories[0].get("name")
        return None

    def _should_exclude(self, categories: list[dict]) -> bool:
        """Check if product should be excluded based on categories."""
        if not self.exclude_categories:
            return False
        slugs = {cat.get("slug", "").lower() for cat in categories}
        # Exclude only if ALL categories are in the exclude set
        return bool(slugs) and slugs.issubset(self.exclude_categories)

    def _extract_weight_from_name(self, name: str) -> Optional[str]:
        """Try to extract weight/size info from product name."""
        m = re.search(
            r"(\d+(?:\.\d+)?\s*(?:g|kg|ml|l|pack)\b)", name, re.IGNORECASE
        )
        return m.group(1) if m else None

    def _parse_wc_product(self, raw: dict) -> Optional[dict]:
        """Parse a WooCommerce product into our standard format."""
        wc_id = raw.get("id")
        name = raw.get("name", "").strip()
        if not name or not wc_id:
            return None

        categories = raw.get("categories", [])

        # Filter out excluded categories
        if self._should_exclude(categories):
            return None

        # Prices — WooCommerce Store API returns prices in cents as strings
        price_str = raw.get("prices", {}).get("price", "0")
        regular_str = raw.get("prices", {}).get("regular_price", "0")
        sale_str = raw.get("prices", {}).get("sale_price", "0")

        try:
            price_cents = int(price_str)
            regular_cents = int(regular_str)
            sale_cents = int(sale_str) if sale_str else 0
        except (ValueError, TypeError):
            price_cents = 0
            regular_cents = 0
            sale_cents = 0

        # Convert cents to dollars
        price_nzd = price_cents / 100
        regular_nzd = regular_cents / 100
        sale_nzd = sale_cents / 100 if sale_cents else None

        if price_nzd <= 0:
            return None

        # Determine promo pricing
        promo_price_nzd = None
        promo_text = None
        if sale_nzd and sale_nzd < regular_nzd:
            promo_price_nzd = sale_nzd
            price_nzd = regular_nzd  # Use regular as base
            saving = regular_nzd - sale_nzd
            promo_text = f"Save ${saving:.2f}"
        elif price_nzd < regular_nzd:
            promo_price_nzd = price_nzd
            price_nzd = regular_nzd
            saving = regular_nzd - promo_price_nzd
            promo_text = f"Save ${saving:.2f}"

        # Image
        images = raw.get("images", [])
        image_url = images[0].get("src") if images else None
        # Use thumbnail if available for smaller size
        if images and images[0].get("thumbnail"):
            image_url = images[0]["thumbnail"]

        # URL
        product_url = raw.get("permalink")

        # Department & category classification
        department = self._get_department(categories)
        wc_category = self._get_wc_category_name(categories)
        category, subcategory = classify_product(department, name)

        # Use WooCommerce category as subcategory if we didn't get one
        if not subcategory and wc_category:
            subcategory = wc_category

        # Size extraction
        size = self._extract_weight_from_name(name)
        structured = parse_structured_size(size or name)

        # Unit pricing — butchers often sell per kg
        unit_price = None
        unit_measure = None
        # Check if price description mentions per kg
        short_desc = raw.get("short_description", "")
        if "per kg" in name.lower() or "per kg" in short_desc.lower() or "/kg" in name.lower():
            unit_price = promo_price_nzd or price_nzd
            unit_measure = "kg"

        # SKU
        sku = raw.get("sku", "")

        return self.build_product_dict(
            source_id=str(wc_id),
            name=name,
            price_nzd=price_nzd,
            promo_price_nzd=promo_price_nzd,
            promo_text=promo_text,
            url=product_url,
            image_url=image_url,
            brand=None,  # Butchers don't typically have brands
            category=category,
            department=department,
            subcategory=subcategory,
            size=size,
            unit_price=unit_price,
            unit_measure=unit_measure,
            volume_ml=structured.volume_ml,
            weight_g=structured.weight_g,
            pack_count=structured.pack_count,
            normalized_name=clean_product_name(name),
            normalized_brand=None,
        )

    # ------------------------------------------------------------------
    # Scraper interface
    # ------------------------------------------------------------------

    async def fetch_catalog_pages(self) -> List[str]:
        """Fetch all products and return as a single JSON page."""
        try:
            products = await self._fetch_all_products()
            return [json.dumps(products)]
        finally:
            await self._close_http_client()

    async def parse_products(self, payload: str) -> List[dict]:
        """Parse a JSON payload of WooCommerce products."""
        raw_products = json.loads(payload)
        parsed: List[dict] = []

        for raw in raw_products:
            try:
                product = self._parse_wc_product(raw)
                if product:
                    parsed.append(product)
            except Exception as e:
                logger.debug(
                    f"[{self.chain}] Error parsing product "
                    f"{raw.get('id', '?')}: {e}"
                )

        logger.info(
            f"[{self.chain}] Parsed {len(parsed)}/{len(raw_products)} products"
        )
        return parsed


__all__ = ["WooCommerceScraper"]
