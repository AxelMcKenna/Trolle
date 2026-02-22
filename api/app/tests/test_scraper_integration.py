"""
Integration tests for scrapers - end-to-end tests with fixtures.

These tests verify the complete scraper pipeline from JSON to product dicts.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.registry import CHAINS, get_chain_scraper
from app.scrapers.countdown_api import CountdownAPIScraper
from app.scrapers.new_world_api import NewWorldAPIScraper
from app.scrapers.paknsave_api import PakNSaveAPIScraper


FIXTURES_DIR = Path(__file__).parent.parent / "scrapers" / "fixtures"


class TestCountdownWithFixture:
    """Test Countdown scraper with real fixture data."""

    @pytest.mark.asyncio
    async def test_parse_fixture_if_exists(self):
        """Test parsing Countdown fixture if available."""
        fixture_path = FIXTURES_DIR / "countdown.html"

        if fixture_path.exists():
            scraper = CountdownAPIScraper()

            with open(fixture_path) as f:
                content = f.read()

            try:
                data = json.loads(content)
                if "products" in data and "items" in data["products"]:
                    products = []
                    for item in data["products"]["items"]:
                        product = scraper._parse_product(item)
                        if product:
                            products.append(product)
                    assert len(products) > 0
            except json.JSONDecodeError:
                pytest.skip("Countdown fixture is HTML, not JSON")
        else:
            pytest.skip("Countdown fixture not found")


class TestProductFieldCompleteness:
    """Test that scrapers produce complete product data."""

    REQUIRED_FIELDS = {
        "chain",
        "source_id",
        "name",
        "price_nzd",
    }

    OPTIONAL_FIELDS = {
        "brand",
        "category",
        "promo_price_nzd",
        "promo_text",
        "promo_ends_at",
        "is_member_only",
        "department",
        "subcategory",
        "size",
        "unit_price",
        "unit_measure",
        "url",
        "image_url",
    }

    @pytest.mark.parametrize("chain_name", list(CHAINS.keys()))
    def test_all_fields_present(self, chain_name):
        """Test that product dicts contain all expected fields."""
        scraper = get_chain_scraper(chain_name)

        product = scraper.build_product_dict(
            source_id="TEST123",
            name="Test Product 500g",
            price_nzd=5.49,
            promo_price_nzd=4.99,
            promo_text="Special",
            is_member_only=True,
            url="https://example.com/product",
            image_url="https://example.com/image.jpg",
        )

        for field in self.REQUIRED_FIELDS:
            assert field in product, f"Missing required field: {field}"
            assert product[field] is not None, f"Required field is None: {field}"

        for field in self.OPTIONAL_FIELDS:
            assert field in product, f"Missing optional field: {field}"


class TestAPIResponseParsing:
    """Test API response parsing for API-based scrapers."""

    def test_countdown_full_response_parsing(self):
        """Test parsing a complete Countdown API response."""
        scraper = CountdownAPIScraper()

        api_response = {
            "products": {
                "items": [
                    {
                        "sku": "123456",
                        "name": "Anchor Milk 2L",
                        "brand": "Anchor",
                        "variety": "Blue Top",
                        "price": {
                            "originalPrice": 5.49,
                            "salePrice": 4.99,
                            "isSpecial": True,
                            "savePrice": 0.50,
                            "isClubPrice": False
                        },
                        "images": {"big": "https://example.com/image.jpg"},
                        "slug": "anchor-milk-2l",
                        "size": {"volumeSize": "2L"}
                    },
                    {
                        "sku": "789012",
                        "name": "Tip Top Bread 700g",
                        "brand": "Tip Top",
                        "variety": "Supersoft",
                        "price": {
                            "originalPrice": 4.50,
                            "isSpecial": False,
                            "isClubPrice": True
                        },
                        "images": {},
                        "slug": "tip-top-bread"
                    }
                ],
                "totalCount": 2
            }
        }

        products = []
        for item in api_response["products"]["items"]:
            product = scraper._parse_product(item)
            products.append(product)

        assert len(products) == 2

        assert products[0]["source_id"] == "123456"
        assert products[0]["price_nzd"] == 5.49
        assert products[0]["promo_price_nzd"] == 4.99
        assert "Anchor" in products[0]["name"]

        assert products[1]["source_id"] == "789012"
        assert products[1]["price_nzd"] == 4.50
        assert products[1]["promo_price_nzd"] is None

    def test_foodstuffs_full_response_parsing(self):
        """Test parsing a complete Foodstuffs API response."""
        scraper = NewWorldAPIScraper(scrape_all_stores=False)

        api_response = {
            "products": [
                {
                    "productId": "R1111111",
                    "brand": "Anchor",
                    "name": "Blue Top Milk",
                    "displayName": "2L",
                    "singlePrice": {"price": 549},
                    "promotions": [
                        {
                            "bestPromotion": True,
                            "rewardValue": 499,
                            "rewardType": "NEW_PRICE",
                            "decal": "3 for $14",
                            "cardDependencyFlag": False
                        }
                    ]
                },
                {
                    "productId": "R2222222",
                    "brand": "Mainland",
                    "name": "Tasty Cheese",
                    "displayName": "500g",
                    "singlePrice": {"price": 999},
                    "promotions": []
                }
            ],
            "totalProducts": 2
        }

        products = []
        for item in api_response["products"]:
            product = scraper._parse_product(item)
            products.append(product)

        assert len(products) == 2

        assert products[0]["price_nzd"] == 5.49
        assert products[0]["promo_price_nzd"] == 4.99
        assert products[0]["promo_text"] == "3 for $14"

        assert products[1]["price_nzd"] == 9.99
        assert products[1]["promo_price_nzd"] is None


class TestMultiStoreHandling:
    """Test handling of multi-store scenarios."""

    def test_new_world_store_specific_pricing(self):
        """Test New World handles store-specific pricing."""
        scraper = NewWorldAPIScraper(scrape_all_stores=False)
        assert hasattr(scraper, 'default_store_id') or hasattr(scraper, 'store_list')

    def test_paknsave_store_specific_pricing(self):
        """Test PAK'nSAVE handles store-specific pricing."""
        scraper = PakNSaveAPIScraper(scrape_all_stores=False)
        assert hasattr(scraper, 'default_store_id') or hasattr(scraper, 'store_list')


class TestStoreDataFiles:
    """Test store data files are valid."""

    DATA_DIR = Path(__file__).parent.parent / "data"

    @pytest.mark.parametrize("chain,expected_min_stores", [
        ("countdown", 50),
        ("newworld", 50),
        ("paknsave", 30),
    ])
    def test_store_data_has_minimum_stores(self, chain, expected_min_stores):
        """Test store data files have minimum number of stores."""
        filename = f"{chain}_stores.json"
        filepath = self.DATA_DIR / filename

        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)

            stores = data if isinstance(data, list) else list(data.values())
            assert len(stores) >= expected_min_stores, \
                f"{chain} has only {len(stores)} stores, expected {expected_min_stores}+"
        else:
            pytest.skip(f"Store data file not found: {filename}")


class TestScraperConfiguration:
    """Test scraper configuration is correct."""

    @pytest.mark.parametrize("chain_name", list(CHAINS.keys()))
    def test_timeout_configured(self, chain_name):
        """Test scrapers have timeouts configured."""
        scraper = get_chain_scraper(chain_name)

        if hasattr(scraper, 'client'):
            assert scraper.client.timeout is not None


class TestScraperSmokeTests:
    """Smoke tests to verify scrapers are operational."""

    @pytest.mark.parametrize("chain_name", list(CHAINS.keys()))
    def test_scraper_can_be_instantiated(self, chain_name):
        """Test all scrapers can be instantiated."""
        scraper = get_chain_scraper(chain_name)

        assert scraper is not None
        assert scraper.chain == chain_name

    @pytest.mark.parametrize("chain_name", list(CHAINS.keys()))
    def test_scraper_has_parse_method(self, chain_name):
        """Test all scrapers have parse_products or equivalent method."""
        scraper = get_chain_scraper(chain_name)

        has_parse = (
            hasattr(scraper, 'parse_products') or
            hasattr(scraper, '_parse_product') or
            hasattr(scraper, 'scrape')
        )
        assert has_parse, f"Scraper {chain_name} missing parse method"

    @pytest.mark.parametrize("chain_name", list(CHAINS.keys()))
    def test_build_product_returns_valid_dict(self, chain_name):
        """Test build_product_dict returns valid product."""
        scraper = get_chain_scraper(chain_name)

        product = scraper.build_product_dict(
            source_id="SMOKE_TEST",
            name="Smoke Test Product 500g",
            price_nzd=10.00
        )

        assert isinstance(product, dict)
        assert product["chain"] == chain_name
        assert product["source_id"] == "SMOKE_TEST"
        assert product["price_nzd"] == 10.00
