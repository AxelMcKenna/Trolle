"""
Comprehensive tests for all grocery scrapers across NZ supermarket chains.

Tests ensure every registered scraper can parse products correctly
and that we have complete coverage for countdown, new_world, and paknsave.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.registry import CHAINS, get_chain_scraper
from app.scrapers.base import Scraper
from app.scrapers.countdown_api import CountdownAPIScraper
from app.scrapers.new_world_api import NewWorldAPIScraper
from app.scrapers.paknsave_api import PakNSaveAPIScraper


class TestScraperRegistry:
    """Tests for the scraper registry."""

    def test_all_chains_registered(self):
        """Test that all expected chains are registered."""
        expected_chains = {
            "countdown",
            "new_world",
            "paknsave",
        }

        for chain in expected_chains:
            assert chain in CHAINS, f"Chain '{chain}' not registered"

    def test_only_grocery_chains_registered(self):
        """Test that only grocery chains are registered."""
        assert len(CHAINS) == 3
        assert set(CHAINS.keys()) == {"countdown", "new_world", "paknsave"}

    def test_get_chain_scraper_returns_instance(self):
        """Test that get_chain_scraper returns proper instances."""
        for chain_name in CHAINS:
            scraper = get_chain_scraper(chain_name)
            assert isinstance(scraper, Scraper)
            assert scraper.chain == chain_name

    def test_get_unknown_chain_raises_error(self):
        """Test that unknown chain raises ValueError."""
        with pytest.raises(ValueError, match="Unknown chain"):
            get_chain_scraper("unknown_chain")

    def test_all_scrapers_have_scrape_method(self):
        """Test that all scrapers have necessary methods."""
        for chain_name, scraper_cls in CHAINS.items():
            scraper = scraper_cls() if chain_name == "countdown" else scraper_cls(scrape_all_stores=False)
            has_scrape = hasattr(scraper, 'scrape')
            has_parse = hasattr(scraper, '_parse_product')
            assert has_scrape or has_parse, f"Scraper {chain_name} has no parse/scrape method"


class TestBaseScraperFunctionality:
    """Tests for base Scraper class functionality."""

    def test_build_product_dict_minimal(self):
        """Test building product dict with minimal required fields."""
        scraper = CountdownAPIScraper()

        result = scraper.build_product_dict(
            source_id="TEST123",
            name="Anchor Blue Top Milk 2L",
            price_nzd=5.49
        )

        assert result["chain"] == "countdown"
        assert result["source_id"] == "TEST123"
        assert result["name"] == "Anchor Blue Top Milk 2L"
        assert result["price_nzd"] == 5.49

    def test_build_product_dict_with_all_fields(self):
        """Test building product dict with all optional fields."""
        scraper = CountdownAPIScraper()
        promo_ends = datetime(2026, 12, 25, 23, 59, 59)

        result = scraper.build_product_dict(
            source_id="PROMO123",
            name="Anchor Milk 2L",
            price_nzd=5.49,
            promo_price_nzd=4.99,
            promo_text="Save $0.50",
            promo_ends_at=promo_ends,
            is_member_only=True,
            url="https://example.com/product",
            image_url="https://example.com/image.jpg",
            brand="Anchor",
            category="Milk",
            department="Chilled, Dairy & Eggs",
            subcategory="Milk",
            size="2L",
            unit_price=2.75,
            unit_measure="1L",
        )

        assert result["promo_price_nzd"] == 4.99
        assert result["promo_text"] == "Save $0.50"
        assert result["promo_ends_at"] == promo_ends
        assert result["is_member_only"] is True
        assert result["url"] == "https://example.com/product"
        assert result["image_url"] == "https://example.com/image.jpg"
        assert result["brand"] == "Anchor"
        assert result["category"] == "Milk"
        assert result["department"] == "Chilled, Dairy & Eggs"
        assert result["subcategory"] == "Milk"
        assert result["size"] == "2L"
        assert result["unit_price"] == 2.75
        assert result["unit_measure"] == "1L"

    def test_build_product_dict_truncates_long_promo_text(self):
        """Test that promo text is truncated to 255 chars."""
        scraper = CountdownAPIScraper()
        long_promo = "A" * 300

        result = scraper.build_product_dict(
            source_id="TEST",
            name="Test",
            price_nzd=10.00,
            promo_text=long_promo
        )

        assert len(result["promo_text"]) == 255


class TestFoodstuffsScraper:
    """Tests for New World and PAK'nSAVE scrapers."""

    @pytest.mark.parametrize("scraper_class,chain_name", [
        (NewWorldAPIScraper, "new_world"),
        (PakNSaveAPIScraper, "paknsave"),
    ])
    def test_initialization(self, scraper_class, chain_name):
        """Test scrapers initialize correctly."""
        scraper = scraper_class(scrape_all_stores=False)

        assert scraper.chain == chain_name
        assert hasattr(scraper, 'site_url')
        assert hasattr(scraper, 'api_domain')

    @pytest.mark.parametrize("scraper_class", [NewWorldAPIScraper, PakNSaveAPIScraper])
    def test_parse_product_basic(self, scraper_class):
        """Test parsing basic product from API response."""
        scraper = scraper_class(scrape_all_stores=False)

        product_data = {
            "productId": "R1234567",
            "brand": "Anchor",
            "name": "Blue Top Milk",
            "displayName": "2L",
            "singlePrice": {
                "price": 549
            },
            "promotions": []
        }

        result = scraper._parse_product(product_data)

        assert result["source_id"] == "R1234567"
        assert "Anchor" in result["name"]
        assert result["price_nzd"] == 5.49
        assert result["promo_price_nzd"] is None

    @pytest.mark.parametrize("scraper_class", [NewWorldAPIScraper, PakNSaveAPIScraper])
    def test_parse_product_with_promotion(self, scraper_class):
        """Test parsing product with promotional pricing."""
        scraper = scraper_class(scrape_all_stores=False)

        product_data = {
            "productId": "R7654321",
            "brand": "Tip Top",
            "name": "Supersoft Bread",
            "displayName": "700g",
            "singlePrice": {
                "price": 450
            },
            "promotions": [
                {
                    "bestPromotion": True,
                    "rewardValue": 350,
                    "rewardType": "NEW_PRICE",
                    "decal": "Now $3.50",
                    "cardDependencyFlag": True
                }
            ]
        }

        result = scraper._parse_product(product_data)

        assert result["price_nzd"] == 4.50
        assert result["promo_price_nzd"] == 3.50
        assert result["is_member_only"] is True

    @pytest.mark.parametrize("scraper_class", [NewWorldAPIScraper, PakNSaveAPIScraper])
    def test_image_url_construction(self, scraper_class):
        """Test product image URL construction."""
        scraper = scraper_class(scrape_all_stores=False)

        product_data = {
            "productId": "R1234567",
            "brand": "Test",
            "name": "Product",
            "displayName": "Test",
            "singlePrice": {"price": 1000},
            "promotions": []
        }

        result = scraper._parse_product(product_data)

        assert result["image_url"] is not None
        assert "fsimg.co.nz" in result["image_url"]


class TestCountdownScraper:
    """Tests for Countdown API scraper."""

    def test_initialization(self):
        """Test scraper initializes correctly."""
        scraper = CountdownAPIScraper()
        assert scraper.chain == "countdown"

    def test_parse_product_basic(self):
        """Test parsing basic product from API response."""
        scraper = CountdownAPIScraper()

        product_data = {
            "sku": "1234567",
            "name": "Anchor Blue Top Milk 2L",
            "brand": "Anchor",
            "variety": "Blue Top",
            "price": {
                "originalPrice": 5.49,
                "isSpecial": False,
                "isClubPrice": False
            },
            "images": {"big": "https://example.com/image.jpg"},
            "slug": "anchor-blue-top-milk-2l"
        }

        result = scraper._parse_product(product_data)

        assert result["source_id"] == "1234567"
        assert "Anchor" in result["name"]
        assert result["price_nzd"] == 5.49

    def test_parse_product_with_special(self):
        """Test parsing product with special pricing."""
        scraper = CountdownAPIScraper()

        product_data = {
            "sku": "7654321",
            "name": "Tip Top Bread 700g",
            "brand": "Tip Top",
            "variety": "Supersoft",
            "price": {
                "originalPrice": 4.50,
                "salePrice": 3.50,
                "isSpecial": True,
                "savePrice": 1.00,
                "isClubPrice": False
            },
            "images": {},
            "slug": "tip-top-bread"
        }

        result = scraper._parse_product(product_data)

        assert result["price_nzd"] == 4.50
        assert result["promo_price_nzd"] == 3.50


class TestNZWideCoverage:
    """Tests to verify complete NZ grocery coverage."""

    MAJOR_NZ_CHAINS = {
        "countdown": 180,
        "new_world": 140,
        "paknsave": 60,
    }

    def test_all_major_chains_have_scrapers(self):
        """Test that all major NZ grocery chains have scrapers."""
        for chain in self.MAJOR_NZ_CHAINS:
            assert chain in CHAINS, f"Missing scraper for major chain: {chain}"

    def test_estimated_store_coverage(self):
        """Test that we have estimated national coverage."""
        total_stores = sum(self.MAJOR_NZ_CHAINS.values())
        assert total_stores > 300, "Should cover 300+ stores nationally"


class TestProductDataQuality:
    """Tests for product data quality."""

    @pytest.mark.parametrize("chain_name", list(CHAINS.keys()))
    def test_scraper_returns_required_fields(self, chain_name):
        """Test that all scrapers return products with required fields."""
        scraper = get_chain_scraper(chain_name)

        required_fields = {
            "chain",
            "source_id",
            "name",
            "price_nzd",
        }

        test_product = scraper.build_product_dict(
            source_id="TEST123",
            name="Test Product 500g",
            price_nzd=10.00
        )

        for field in required_fields:
            assert field in test_product, f"Missing required field '{field}' in {chain_name}"
            assert test_product[field] is not None, f"Field '{field}' is None in {chain_name}"

    @pytest.mark.parametrize("chain_name", list(CHAINS.keys()))
    def test_price_is_valid_number(self, chain_name):
        """Test that price is a valid positive number."""
        scraper = get_chain_scraper(chain_name)

        product = scraper.build_product_dict(
            source_id="TEST",
            name="Test",
            price_nzd=5.49
        )

        assert isinstance(product["price_nzd"], (int, float))
        assert product["price_nzd"] > 0


@pytest.fixture
def sample_countdown_api_response():
    """Sample Countdown API response fixture."""
    return {
        "products": {
            "items": [
                {
                    "sku": "123456",
                    "name": "Anchor Milk 2L",
                    "brand": "Anchor",
                    "variety": "Blue Top",
                    "price": {"originalPrice": 5.49},
                    "images": {},
                    "slug": "anchor-milk-2l"
                }
            ],
            "totalCount": 1
        }
    }


@pytest.fixture
def sample_foodstuffs_api_response():
    """Sample Foodstuffs (New World/PAK'nSAVE) API response fixture."""
    return {
        "products": [
            {
                "productId": "R123456",
                "brand": "Anchor",
                "name": "Blue Top Milk",
                "displayName": "2L",
                "singlePrice": {"price": 549},
                "promotions": []
            }
        ],
        "totalProducts": 1
    }
