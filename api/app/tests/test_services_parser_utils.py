"""Tests for parser utilities."""
from __future__ import annotations

import pytest

from app.services.parser_utils import (
    CATEGORY_HIERARCHY,
    format_product_name,
    parse_size,
)


class TestParseSize:
    """Tests for size parsing."""

    def test_parse_size_grams(self):
        """Should parse gram sizes."""
        assert parse_size("Butter 500g") == "500g"

    def test_parse_size_kilograms(self):
        """Should parse kilogram sizes."""
        assert parse_size("Apples 1kg") == "1kg"

    def test_parse_size_decimal_kg(self):
        """Should parse decimal kilogram sizes."""
        result = parse_size("Rice 1.5kg")
        assert result is not None
        assert "1.5" in result

    def test_parse_size_ml(self):
        """Should parse millilitre sizes."""
        assert parse_size("Juice 500ml") == "500ml"

    def test_parse_size_litres(self):
        """Should parse litre sizes."""
        result = parse_size("Milk 2l")
        assert result is not None
        assert "2" in result

    def test_parse_size_litre_variations(self):
        """Should handle various litre spellings."""
        for text in ["Milk 1 litre", "Milk 1 ltr", "Milk 1l"]:
            result = parse_size(text)
            assert result is not None, f"Failed for: {text}"

    def test_parse_size_pack(self):
        """Should parse pack sizes."""
        result = parse_size("Eggs 6pack")
        assert result is not None
        assert "6" in result

    def test_parse_size_each(self):
        """Should parse each/ea sizes."""
        result = parse_size("Avocado 1ea")
        assert result is not None
        assert "1" in result

    def test_parse_size_no_match(self):
        """Should return None when no size found."""
        assert parse_size("Banana") is None
        assert parse_size("Fresh Bread") is None

    def test_parse_size_empty_string(self):
        """Should return None for empty string."""
        assert parse_size("") is None

    def test_parse_size_none_input(self):
        """Should return None for None-like input."""
        assert parse_size("") is None

    def test_parse_size_case_insensitive(self):
        """Should handle different cases."""
        assert parse_size("Cheese 250G") is not None
        assert parse_size("Milk 2L") is not None
        assert parse_size("Yoghurt 500ML") is not None


class TestFormatProductName:
    """Tests for product name formatting."""

    def test_normalizes_whitespace(self):
        """Should normalize multiple spaces."""
        result = format_product_name("Anchor   Blue  Top   Milk")
        assert result == "Anchor Blue Top Milk"

    def test_strips_leading_trailing_whitespace(self):
        """Should strip leading/trailing whitespace."""
        result = format_product_name("  Anchor Milk  ")
        assert result == "Anchor Milk"

    def test_empty_string(self):
        """Should handle empty string."""
        result = format_product_name("")
        assert result == ""

    def test_preserves_normal_name(self):
        """Should preserve properly formatted names."""
        result = format_product_name("Countdown Fresh Whole Chicken")
        assert result == "Countdown Fresh Whole Chicken"

    def test_with_brand(self):
        """Should accept optional brand parameter."""
        result = format_product_name("Blue Top Milk 2L", brand="Anchor")
        assert result == "Blue Top Milk 2L"

    def test_tabs_and_newlines(self):
        """Should normalize tabs and newlines."""
        result = format_product_name("Product\t\tName\n2L")
        assert result == "Product Name 2L"


class TestCategoryHierarchy:
    """Tests for grocery category hierarchy mapping."""

    def test_fruit_and_veg_subcategories(self):
        """Fruit & Veg subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Fruit"] == "Fruit & Vegetables"
        assert CATEGORY_HIERARCHY["Vegetables"] == "Fruit & Vegetables"
        assert CATEGORY_HIERARCHY["Salad"] == "Fruit & Vegetables"

    def test_meat_and_seafood_subcategories(self):
        """Meat & Seafood subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Beef & Veal"] == "Meat & Seafood"
        assert CATEGORY_HIERARCHY["Chicken"] == "Meat & Seafood"
        assert CATEGORY_HIERARCHY["Pork"] == "Meat & Seafood"
        assert CATEGORY_HIERARCHY["Seafood"] == "Meat & Seafood"

    def test_dairy_subcategories(self):
        """Dairy subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Milk"] == "Chilled, Dairy & Eggs"
        assert CATEGORY_HIERARCHY["Cheese"] == "Chilled, Dairy & Eggs"
        assert CATEGORY_HIERARCHY["Yoghurt"] == "Chilled, Dairy & Eggs"
        assert CATEGORY_HIERARCHY["Eggs"] == "Chilled, Dairy & Eggs"

    def test_bakery_subcategories(self):
        """Bakery subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Bread"] == "Bakery"
        assert CATEGORY_HIERARCHY["Rolls & Buns"] == "Bakery"

    def test_pantry_subcategories(self):
        """Pantry subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Canned Goods"] == "Pantry"
        assert CATEGORY_HIERARCHY["Pasta, Rice & Noodles"] == "Pantry"
        assert CATEGORY_HIERARCHY["Sauces & Condiments"] == "Pantry"

    def test_frozen_subcategories(self):
        """Frozen subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Frozen Vegetables"] == "Frozen"
        assert CATEGORY_HIERARCHY["Ice Cream & Desserts"] == "Frozen"
        assert CATEGORY_HIERARCHY["Frozen Pizza"] == "Frozen"

    def test_drinks_subcategories(self):
        """Drinks subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Water"] == "Drinks"
        assert CATEGORY_HIERARCHY["Soft Drinks"] == "Drinks"
        assert CATEGORY_HIERARCHY["Coffee"] == "Drinks"

    def test_snacks_subcategories(self):
        """Snacks subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Chips & Crackers"] == "Snacks & Confectionery"
        assert CATEGORY_HIERARCHY["Chocolate"] == "Snacks & Confectionery"
        assert CATEGORY_HIERARCHY["Biscuits"] == "Snacks & Confectionery"

    def test_household_subcategories(self):
        """Household subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Cleaning"] == "Household"
        assert CATEGORY_HIERARCHY["Laundry"] == "Household"

    def test_baby_subcategories(self):
        """Baby subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Nappies"] == "Baby & Child"
        assert CATEGORY_HIERARCHY["Baby Food"] == "Baby & Child"

    def test_pet_subcategories(self):
        """Pet subcategories should map correctly."""
        assert CATEGORY_HIERARCHY["Dog Food"] == "Pet"
        assert CATEGORY_HIERARCHY["Cat Food"] == "Pet"

    def test_hierarchy_is_not_empty(self):
        """Category hierarchy should contain many entries."""
        assert len(CATEGORY_HIERARCHY) > 30
