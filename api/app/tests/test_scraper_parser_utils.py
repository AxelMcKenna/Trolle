"""
Comprehensive tests for parser_utils.py - Size parsing, name formatting, and category hierarchy.

Tests all parsing functions used by scrapers to normalize grocery product data.
"""
from __future__ import annotations

import pytest

from app.services.parser_utils import (
    CATEGORY_HIERARCHY,
    format_product_name,
    parse_size,
)


class TestParseSize:
    """Comprehensive tests for parse_size function."""

    @pytest.mark.parametrize("text,expected", [
        ("Butter 500g", "500g"),
        ("Flour 1kg", "1kg"),
        ("Rice 1.5kg", "1.5kg"),
        ("Juice 500ml", "500ml"),
        ("Cream 300ml", "300ml"),
        ("Eggs 6pk", "6pk"),
    ])
    def test_standard_sizes(self, text, expected):
        """Test parsing of standard grocery size formats."""
        result = parse_size(text)
        assert result == expected, f"Expected '{expected}' for '{text}', got '{result}'"

    @pytest.mark.parametrize("text", [
        ("Anchor Milk 2l"),
        ("Milk 1 litre"),
        ("Juice 1 ltr"),
        ("Water 2L"),
    ])
    def test_litre_variations(self, text):
        """Test various litre format spellings."""
        result = parse_size(text)
        assert result is not None, f"Failed to parse size from: {text}"

    @pytest.mark.parametrize("text", [
        "Fresh Bananas",
        "Organic Broccoli",
        "Free Range Chicken",
        "",
        "Product Name Only",
    ])
    def test_no_size_found(self, text):
        """Test handling of text without size information."""
        result = parse_size(text)
        assert result is None

    def test_size_case_insensitivity(self):
        """Test that size parsing is case insensitive."""
        variants = [
            "Cheese 250g",
            "Cheese 250G",
            "Milk 1L",
            "Milk 1l",
            "Juice 500ML",
            "Juice 500ml",
        ]

        for text in variants:
            result = parse_size(text)
            assert result is not None, f"Failed for: {text}"

    def test_parse_each_unit(self):
        """Test parsing 'each' unit sizes."""
        result = parse_size("Avocado 1each")
        assert result is not None

    def test_parse_pack_format(self):
        """Test parsing pack format sizes."""
        result = parse_size("Toilet Paper 12pack")
        assert result is not None
        assert "12" in result


class TestFormatProductName:
    """Comprehensive tests for format_product_name function."""

    def test_normalizes_multiple_spaces(self):
        """Test normalization of multiple spaces."""
        result = format_product_name("Anchor   Blue   Top   Milk   2L")
        assert result == "Anchor Blue Top Milk 2L"

    def test_strips_whitespace(self):
        """Test stripping of leading/trailing whitespace."""
        result = format_product_name("  Countdown Bread  ")
        assert result == "Countdown Bread"

    def test_empty_string(self):
        """Test handling of empty string."""
        result = format_product_name("")
        assert result == ""

    def test_preserves_proper_names(self):
        """Test that properly formatted names are unchanged."""
        name = "Tip Top Supersoft White Bread 700g"
        result = format_product_name(name)
        assert result == name

    def test_with_brand_parameter(self):
        """Test with optional brand parameter."""
        result = format_product_name("Whole Milk 2L", brand="Anchor")
        assert result == "Whole Milk 2L"


class TestCategoryHierarchyComprehensive:
    """Comprehensive tests for category hierarchy mapping."""

    def test_all_departments_present(self):
        """Test that all major grocery departments are represented."""
        departments = set(CATEGORY_HIERARCHY.values())
        expected_departments = {
            "Fruit & Vegetables",
            "Meat & Seafood",
            "Chilled, Dairy & Eggs",
            "Bakery",
            "Pantry",
            "Frozen",
            "Drinks",
            "Snacks & Confectionery",
            "Household",
            "Baby & Child",
            "Pet",
        }
        for dept in expected_departments:
            assert dept in departments, f"Missing department: {dept}"

    def test_subcategories_are_strings(self):
        """Test that all keys and values are strings."""
        for subcat, dept in CATEGORY_HIERARCHY.items():
            assert isinstance(subcat, str)
            assert isinstance(dept, str)

    def test_no_duplicate_subcategories(self):
        """Test that subcategory names are unique."""
        subcategories = list(CATEGORY_HIERARCHY.keys())
        assert len(subcategories) == len(set(subcategories))

    @pytest.mark.parametrize("subcategory,expected_department", [
        ("Fruit", "Fruit & Vegetables"),
        ("Vegetables", "Fruit & Vegetables"),
        ("Beef & Veal", "Meat & Seafood"),
        ("Chicken", "Meat & Seafood"),
        ("Milk", "Chilled, Dairy & Eggs"),
        ("Cheese", "Chilled, Dairy & Eggs"),
        ("Bread", "Bakery"),
        ("Canned Goods", "Pantry"),
        ("Frozen Vegetables", "Frozen"),
        ("Water", "Drinks"),
        ("Chips & Crackers", "Snacks & Confectionery"),
        ("Cleaning", "Household"),
        ("Nappies", "Baby & Child"),
        ("Dog Food", "Pet"),
    ])
    def test_specific_mappings(self, subcategory, expected_department):
        """Test specific subcategory to department mappings."""
        assert CATEGORY_HIERARCHY[subcategory] == expected_department


class TestParserIntegration:
    """Integration tests combining parser functions."""

    @pytest.mark.parametrize("product_name", [
        "Anchor Blue Top Milk 2L",
        "Tip Top Supersoft White Bread 700g",
        "Sanitarium Weet-Bix 750g",
        "Coca-Cola Original 1.5l",
        "Mainland Tasty Cheese 500g",
    ])
    def test_full_product_parsing(self, product_name):
        """Test that all parsers work together on real grocery product names."""
        size = parse_size(product_name)
        formatted = format_product_name(product_name)

        assert size is not None, f"No size found for: {product_name}"
        assert formatted == product_name.strip()

    def test_minimal_product_name(self):
        """Test parsing with minimal product names."""
        size = parse_size("Bananas")
        formatted = format_product_name("Bananas")

        assert size is None
        assert formatted == "Bananas"
