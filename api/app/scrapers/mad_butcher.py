"""Mad Butcher scraper using WooCommerce Store API.

Mad Butcher is NZ's largest butcher chain (~19 stores).
Their WooCommerce site exposes a public Store API at
``wp-json/wc/store/v1/products`` with ~40 SKUs.

Pricing is national (same across all stores).
"""
from __future__ import annotations

from app.scrapers.woocommerce_base import WooCommerceScraper


class MadButcherScraper(WooCommerceScraper):
    chain = "mad_butcher"
    site_url = "https://www.madbutcher.co.nz"

    # Exclude non-food categories if they appear
    exclude_categories: set[str] = {"knives", "pets", "pet"}


__all__ = ["MadButcherScraper"]
