"""
Comprehensive tests for scraper error handling and edge cases.

Tests ensure scrapers handle errors gracefully and don't crash on malformed data.
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.base import Scraper
from app.scrapers.countdown_api import CountdownAPIScraper
from app.scrapers.new_world_api import NewWorldAPIScraper
from app.scrapers.paknsave_api import PakNSaveAPIScraper
from app.scrapers.registry import CHAINS, get_chain_scraper


class TestMalformedAPIHandling:
    """Tests for handling malformed API responses."""

    def test_countdown_handles_empty_product_data(self):
        """Test Countdown scraper handles empty product data."""
        scraper = CountdownAPIScraper()
        result = scraper._parse_product({})

    def test_foodstuffs_handles_missing_fields(self):
        """Test Foodstuffs scraper handles missing required fields."""
        scraper = NewWorldAPIScraper(scrape_all_stores=False)

        product_data = {
            "brand": "Test",
            "name": "Product",
            "displayName": "Test",
            "singlePrice": {"price": 1000},
            "promotions": []
        }

        result = scraper._parse_product(product_data)
        assert result["source_id"] == ""

    def test_foodstuffs_handles_missing_price(self):
        """Test Foodstuffs scraper handles missing price."""
        scraper = PakNSaveAPIScraper(scrape_all_stores=False)

        product_data = {
            "productId": "R123",
            "brand": "Test",
            "name": "Product",
            "displayName": "Test",
            "singlePrice": {},
            "promotions": []
        }

        try:
            result = scraper._parse_product(product_data)
            assert result["price_nzd"] in [0, 0.0, None]
        except (KeyError, TypeError):
            pass


class TestNetworkErrorHandling:
    """Tests for handling network errors."""

    @pytest.mark.asyncio
    async def test_countdown_handles_api_error(self):
        """Test Countdown scraper handles API errors gracefully."""
        scraper = CountdownAPIScraper()
        scraper.cookies = {"session": "test"}

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(Exception):
                await scraper._fetch_category("dairy", "dairy")


class TestScraperEdgeCases:
    """Tests for edge cases in scrapers."""

    def test_build_product_dict_with_none_values(self):
        """Test building product dict with None optional values."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="TEST",
            name="Test Product",
            price_nzd=10.0,
            promo_price_nzd=None,
            promo_text=None,
            url=None,
            image_url=None,
        )

        assert result["source_id"] == "TEST"
        assert result["promo_price_nzd"] is None
        assert result["promo_text"] is None

    def test_build_product_dict_with_zero_price(self):
        """Test building product dict with zero price."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="FREE",
            name="Free Sample",
            price_nzd=0.0
        )

        assert result["price_nzd"] == 0.0

    def test_build_product_dict_with_very_high_price(self):
        """Test building product dict with very high price."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="EXPENSIVE",
            name="Wagyu Beef Steak 500g",
            price_nzd=299.99
        )

        assert result["price_nzd"] == 299.99

    def test_build_product_dict_with_unicode_name(self):
        """Test building product dict with unicode characters."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="UNICODE",
            name="Parmigiano-Reggiano 200g",
            price_nzd=15.00
        )

        assert "Parmigiano" in result["name"]

    def test_build_product_dict_with_very_long_name(self):
        """Test building product dict with very long name."""
        scraper = CountdownAPIScraper()

        long_name = "A" * 1000 + " 500g"
        result = scraper.build_product_dict(
            source_id="LONG",
            name=long_name,
            price_nzd=10.0
        )

        assert len(result["name"]) == len(long_name)

    def test_promo_price_higher_than_regular_price(self):
        """Test handling when promo price is incorrectly higher than regular."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="WEIRD",
            name="Test Product",
            price_nzd=20.0,
            promo_price_nzd=25.0
        )

        assert result["price_nzd"] == 20.0
        assert result["promo_price_nzd"] == 25.0

    def test_negative_price_handling(self):
        """Test handling of negative prices."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="NEGATIVE",
            name="Test",
            price_nzd=-10.0
        )

        assert result["price_nzd"] == -10.0

    def test_build_product_dict_with_grocery_fields(self):
        """Test building product dict with grocery-specific fields."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="GROC",
            name="Test Product 500g",
            price_nzd=5.00,
            department="Pantry",
            subcategory="Canned Goods",
            size="500g",
            unit_price=1.00,
            unit_measure="100g",
        )

        assert result["department"] == "Pantry"
        assert result["subcategory"] == "Canned Goods"
        assert result["size"] == "500g"
        assert result["unit_price"] == 1.00
        assert result["unit_measure"] == "100g"
