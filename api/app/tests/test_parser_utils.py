"""Tests for parser_utils module."""
from app.services.parser_utils import CATEGORY_HIERARCHY, format_product_name, parse_size


def test_parse_size_grams():
    result = parse_size("Anchor Butter 500g")
    assert result == "500g"


def test_parse_size_kilograms():
    result = parse_size("Royal Gala Apples 1kg")
    assert result == "1kg"


def test_parse_size_ml():
    result = parse_size("Anchor Milk 2L")
    assert result is not None
    assert "2" in result


def test_parse_size_pack():
    result = parse_size("Coca-Cola 6pack")
    assert result is not None
    assert "6" in result


def test_parse_size_no_match():
    result = parse_size("Banana")
    assert result is None


def test_parse_size_empty():
    result = parse_size("")
    assert result is None


def test_format_product_name_normalizes_whitespace():
    result = format_product_name("  Anchor   Blue  Top  Milk  ")
    assert result == "Anchor Blue Top Milk"


def test_format_product_name_empty():
    result = format_product_name("")
    assert result == ""


def test_category_hierarchy_has_grocery_departments():
    assert CATEGORY_HIERARCHY["Milk"] == "Chilled, Dairy & Eggs"
    assert CATEGORY_HIERARCHY["Bread"] == "Bakery"
    assert CATEGORY_HIERARCHY["Fruit"] == "Fruit & Vegetables"
    assert CATEGORY_HIERARCHY["Chicken"] == "Meat & Seafood"
