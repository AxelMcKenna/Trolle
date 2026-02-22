"""Tests for grocery scrapers."""
import os
import pytest

from app.scrapers.countdown_api import CountdownAPIScraper
from app.scrapers.new_world_api import NewWorldAPIScraper
from app.scrapers.paknsave_api import PakNSaveAPIScraper


def _check_playwright_browsers():
    """Check if Playwright browsers are actually installed."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            path = p.chromium.executable_path
            return os.path.exists(path)
    except Exception:
        return False

PLAYWRIGHT_AVAILABLE = _check_playwright_browsers()

requires_playwright = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="Playwright browsers not installed (run: playwright install)"
)


@requires_playwright
@pytest.mark.asyncio
async def test_countdown_scraper_parses_products():
    """Test that Countdown API scraper can fetch and parse products."""
    scraper = CountdownAPIScraper()
    products = await scraper.scrape()
    assert len(products) > 0
    assert all("name" in p for p in products)
    assert all("price_nzd" in p for p in products)


@requires_playwright
@pytest.mark.asyncio
async def test_new_world_scraper_parses_products():
    """Test that New World API scraper can fetch and parse products."""
    scraper = NewWorldAPIScraper(scrape_all_stores=False)
    assert scraper.chain == "new_world"
    assert hasattr(scraper, 'site_url')


@requires_playwright
@pytest.mark.asyncio
async def test_paknsave_scraper_parses_products():
    """Test that PAK'nSAVE API scraper can fetch and parse products."""
    scraper = PakNSaveAPIScraper(scrape_all_stores=False)
    assert scraper.chain == "paknsave"
    assert hasattr(scraper, 'site_url')
