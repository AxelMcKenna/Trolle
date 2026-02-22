from __future__ import annotations

import re
from typing import Optional

SIZE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:kg|g|ml|l|ltr|litre|litres|liters|pk|pack|ea|each))",
    re.IGNORECASE,
)

# Grocery category hierarchy: maps subcategories to parent departments
CATEGORY_HIERARCHY = {
    # Fruit & Vegetables
    "Fruit": "Fruit & Vegetables",
    "Vegetables": "Fruit & Vegetables",
    "Salad": "Fruit & Vegetables",
    "Organic Fruit & Vegetables": "Fruit & Vegetables",
    # Meat & Seafood
    "Beef & Veal": "Meat & Seafood",
    "Chicken": "Meat & Seafood",
    "Pork": "Meat & Seafood",
    "Lamb": "Meat & Seafood",
    "Mince & Patties": "Meat & Seafood",
    "Sausages & Burgers": "Meat & Seafood",
    "Seafood": "Meat & Seafood",
    "Deli & Cooked Meats": "Meat & Seafood",
    # Dairy
    "Milk": "Chilled, Dairy & Eggs",
    "Cheese": "Chilled, Dairy & Eggs",
    "Yoghurt": "Chilled, Dairy & Eggs",
    "Eggs": "Chilled, Dairy & Eggs",
    "Butter & Margarine": "Chilled, Dairy & Eggs",
    "Cream & Sour Cream": "Chilled, Dairy & Eggs",
    # Bakery
    "Bread": "Bakery",
    "Rolls & Buns": "Bakery",
    "Wraps, Pita & Flatbread": "Bakery",
    "Cakes & Muffins": "Bakery",
    # Pantry
    "Canned Goods": "Pantry",
    "Pasta, Rice & Noodles": "Pantry",
    "Sauces & Condiments": "Pantry",
    "Baking": "Pantry",
    "Breakfast Cereals": "Pantry",
    "Spreads": "Pantry",
    "Oil & Vinegar": "Pantry",
    # Frozen
    "Frozen Vegetables": "Frozen",
    "Frozen Meals": "Frozen",
    "Ice Cream & Desserts": "Frozen",
    "Frozen Chips & Wedges": "Frozen",
    "Frozen Meat & Seafood": "Frozen",
    "Frozen Pizza": "Frozen",
    # Drinks
    "Water": "Drinks",
    "Soft Drinks": "Drinks",
    "Juice": "Drinks",
    "Coffee": "Drinks",
    "Tea": "Drinks",
    "Energy & Sports Drinks": "Drinks",
    # Snacks
    "Chips & Crackers": "Snacks & Confectionery",
    "Chocolate": "Snacks & Confectionery",
    "Biscuits": "Snacks & Confectionery",
    "Nuts & Dried Fruit": "Snacks & Confectionery",
    "Lollies": "Snacks & Confectionery",
    # Household
    "Cleaning": "Household",
    "Laundry": "Household",
    "Toilet Paper & Tissues": "Household",
    # Baby
    "Nappies": "Baby & Child",
    "Baby Food": "Baby & Child",
    # Pet
    "Dog Food": "Pet",
    "Cat Food": "Pet",
}


def parse_size(text: str) -> Optional[str]:
    """Extract product size from text, e.g. '500g', '1L', '6 pack'."""
    if not text:
        return None
    match = SIZE_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def format_product_name(name: str, brand: Optional[str] = None) -> str:
    """Format a product name for display. Grocery API names are generally clean."""
    if not name:
        return name
    # Normalize whitespace
    return " ".join(name.split())


__all__ = [
    "CATEGORY_HIERARCHY",
    "parse_size",
    "format_product_name",
]
