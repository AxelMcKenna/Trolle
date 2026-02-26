"""
Comprehensive test suite for Troll-E scrapers.

Tests cover:
- Product parsing accuracy
- Price extraction
- Promotional pricing
- Error handling
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from app.scrapers.countdown_api import CountdownAPIScraper
from app.scrapers.new_world_api import NewWorldAPIScraper
from app.scrapers.paknsave_api import PakNSaveAPIScraper


@pytest.fixture
def countdown_api_response():
    """Sample Countdown API response."""
    return {
        "products": {
            "items": [
                {
                    "sku": "1234567",
                    "name": "Anchor Blue Top Milk 2L",
                    "brand": "Anchor",
                    "variety": "Blue Top",
                    "price": {
                        "originalPrice": 5.49,
                        "salePrice": 4.99,
                        "isSpecial": True,
                        "savePrice": 0.50,
                        "isClubPrice": False
                    },
                    "size": {
                        "volumeSize": "2L",
                        "cupPrice": "$2.75 per 1L"
                    },
                    "images": {
                        "big": "https://example.com/milk.jpg"
                    },
                    "slug": "anchor-blue-top-milk-2l"
                },
                {
                    "sku": "7654321",
                    "name": "Tip Top Supersoft White Bread 700g",
                    "brand": "Tip Top",
                    "variety": "Supersoft",
                    "price": {
                        "originalPrice": 4.50,
                        "isSpecial": False,
                        "isClubPrice": False
                    },
                    "images": {
                        "big": "https://example.com/bread.jpg"
                    },
                    "slug": "tip-top-supersoft-white-bread"
                }
            ],
            "totalCount": 2
        }
    }


@pytest.fixture
def foodstuffs_api_response():
    """Sample New World/PAK'nSAVE API response."""
    return {
        "products": [
            {
                "productId": "R1234567",
                "brand": "Anchor",
                "name": "Blue Top Milk",
                "displayName": "2L",
                "singlePrice": {
                    "price": 549
                },
                "promotions": [
                    {
                        "bestPromotion": True,
                        "rewardValue": 499,
                        "rewardType": "NEW_PRICE",
                        "decal": "Now $4.99",
                        "cardDependencyFlag": True
                    }
                ]
            },
            {
                "productId": "R7654321",
                "brand": "Tip Top",
                "name": "Supersoft White Bread",
                "displayName": "700g",
                "singlePrice": {
                    "price": 450
                },
                "promotions": []
            }
        ],
        "totalProducts": 2
    }


class TestCountdownScraper:
    """Test Countdown API scraper."""

    def test_parse_product_with_promo(self, countdown_api_response):
        """Test parsing product with promotional pricing."""
        scraper = CountdownAPIScraper()
        product_data = countdown_api_response["products"]["items"][0]

        result = scraper._parse_product(product_data)

        assert result["source_id"] == "1234567"
        assert "Anchor" in result["name"]
        assert result["price_nzd"] == 5.49
        assert result["promo_price_nzd"] == 4.99
        assert result["promo_text"] == "Save $0.50"
        assert result["is_member_only"] is False
        assert result["image_url"] is not None
        assert result["url"] is not None

    def test_parse_product_no_promo(self, countdown_api_response):
        """Test parsing product without promotion."""
        scraper = CountdownAPIScraper()
        product_data = countdown_api_response["products"]["items"][1]

        result = scraper._parse_product(product_data)

        assert result["source_id"] == "7654321"
        assert result["price_nzd"] == 4.50
        assert result["promo_price_nzd"] is None
        assert result["promo_text"] is None

    @pytest.mark.asyncio
    async def test_fetch_search(self):
        """Test search fetching with mocked HTTP client."""
        scraper = CountdownAPIScraper()
        scraper.cookies = {"session": "test"}

        mock_response_data = {"products": {"items": []}}

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_get = AsyncMock(return_value=mock_response)
            mock_instance.get = mock_get
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scraper._fetch_search("milk")

            assert "products" in result
            assert result == mock_response_data


class TestFoodstuffsScraper:
    """Test New World and PAK'nSAVE scrapers (shared API)."""

    @pytest.mark.parametrize("scraper_class", [NewWorldAPIScraper, PakNSaveAPIScraper])
    def test_parse_product_with_member_promo(self, scraper_class, foodstuffs_api_response):
        """Test parsing product with member-only promotion."""
        scraper = scraper_class(scrape_all_stores=False)
        product_data = foodstuffs_api_response["products"][0]

        result = scraper._parse_product(product_data)

        assert result["source_id"] == "R1234567"
        assert "Anchor" in result["name"]
        assert result["price_nzd"] == 5.49
        assert result["promo_price_nzd"] == 4.99
        assert result["promo_text"] == "Now $4.99"
        assert result["is_member_only"] is True

    @pytest.mark.parametrize("scraper_class", [NewWorldAPIScraper, PakNSaveAPIScraper])
    def test_parse_product_no_promo(self, scraper_class, foodstuffs_api_response):
        """Test parsing product without promotion."""
        scraper = scraper_class(scrape_all_stores=False)
        product_data = foodstuffs_api_response["products"][1]

        result = scraper._parse_product(product_data)

        assert result["source_id"] == "R7654321"
        assert result["price_nzd"] == 4.50
        assert result["promo_price_nzd"] is None
        assert result["is_member_only"] is False

    @pytest.mark.parametrize("scraper_class", [NewWorldAPIScraper, PakNSaveAPIScraper])
    def test_image_url_construction(self, scraper_class, foodstuffs_api_response):
        """Test product image URL is properly constructed."""
        scraper = scraper_class(scrape_all_stores=False)
        product_data = foodstuffs_api_response["products"][0]

        result = scraper._parse_product(product_data)

        assert result["image_url"] is not None
        assert "fsimg.co.nz" in result["image_url"]
        assert "400x400" in result["image_url"]

    @pytest.mark.parametrize("scraper_class", [NewWorldAPIScraper, PakNSaveAPIScraper])
    def test_product_url_construction(self, scraper_class, foodstuffs_api_response):
        """Test product URL is properly constructed."""
        scraper = scraper_class(scrape_all_stores=False)
        product_data = foodstuffs_api_response["products"][0]

        result = scraper._parse_product(product_data)

        assert result["url"] is not None
        assert "/shop/product/" in result["url"]
        assert "r1234567" in result["url"].lower()


class TestBaseScraper:
    """Test base scraper functionality shared across all scrapers."""

    def test_build_product_dict_minimal(self):
        """Test building product dict with minimal data."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="TEST123",
            name="Anchor Milk 2L",
            price_nzd=5.49
        )

        assert result["source_id"] == "TEST123"
        assert result["name"] == "Anchor Milk 2L"
        assert result["price_nzd"] == 5.49
        assert result["chain"] == "countdown"

    def test_build_product_dict_with_promo(self):
        """Test building product dict with promotional pricing."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="PROMO123",
            name="Bread 700g",
            price_nzd=4.50,
            promo_price_nzd=3.50,
            promo_text="Save $1",
            is_member_only=True
        )

        assert result["promo_price_nzd"] == 3.50
        assert result["promo_text"] == "Save $1"
        assert result["is_member_only"] is True

    def test_build_product_dict_with_grocery_fields(self):
        """Test building product dict with grocery-specific fields."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="GROC123",
            name="Anchor Blue Top Milk 2L",
            price_nzd=5.49,
            brand="Anchor",
            category="Milk",
            department="Chilled, Dairy & Eggs",
            subcategory="Milk",
            size="2L",
            unit_price=2.75,
            unit_measure="1L",
        )

        assert result["brand"] == "Anchor"
        assert result["department"] == "Chilled, Dairy & Eggs"
        assert result["subcategory"] == "Milk"
        assert result["size"] == "2L"
        assert result["unit_price"] == 2.75
        assert result["unit_measure"] == "1L"


class TestErrorHandling:
    """Test error handling in scrapers."""

    @pytest.mark.asyncio
    async def test_countdown_handles_invalid_response(self):
        """Test Countdown scraper handles invalid API responses."""
        scraper = CountdownAPIScraper()
        products = scraper._parse_product({})


class TestScraperIntegration:
    """Integration tests for complete scraper pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_countdown_scrape_single_category(self):
        """Test scraping a single search term returns valid products."""
        scraper = CountdownAPIScraper()

        mock_search_response = {
            "products": {
                "items": [
                    {
                        "sku": "TEST123",
                        "name": "Anchor Milk 2L",
                        "brand": "Anchor",
                        "variety": "Blue Top",
                        "price": {"originalPrice": 5.49},
                        "images": {},
                        "slug": "anchor-milk-2l",
                        "departments": [{"name": "Chilled, Dairy & Eggs"}],
                    }
                ]
            }
        }

        scraper.cookies = {"session": "test"}
        with patch.object(scraper, '_fetch_search', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_search_response

            products = await scraper.scrape()

            assert len(products) > 0
            assert all("source_id" in p for p in products)
            assert all("price_nzd" in p for p in products)


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session
