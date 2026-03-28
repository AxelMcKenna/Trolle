"""Preston's Master Butchers scraper using WooCommerce Store API.

Preston's is a Wellington-based butcher chain (2 stores: Porirua & Wellington).
Their WooCommerce site exposes a public Store API at
``wp-json/wc/store/v1/products`` with ~200 SKUs including meat,
smallgoods, pantry items, and BBQ accessories.

Pricing is national (same across both stores).
"""
from __future__ import annotations

from app.scrapers.woocommerce_base import WooCommerceScraper


class PrestonsScraper(WooCommerceScraper):
    chain = "prestons"
    site_url = "https://www.prestonsmasterbutchers.co.nz"

    # Exclude non-food items
    exclude_categories: set[str] = {"knives", "pets", "pet"}


__all__ = ["PrestonsScraper"]
