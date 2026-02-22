"""Rule-based category mapper for Woolworths/Countdown products.

Maps the Woolworths ``department`` field and product name keywords to our
canonical ``category`` and ``subcategory`` values that align with the
frontend CategoryFilter and the CATEGORY_HIERARCHY in parser_utils.
"""
from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Stage 1: Department → Category
# ---------------------------------------------------------------------------

DEPARTMENT_TO_CATEGORY: dict[str, str] = {
    "Fridge & Deli": "Chilled, Dairy & Eggs",
    "Meat & Poultry": "Meat & Seafood",
    "Fish & Seafood": "Meat & Seafood",
    "Fruit & Veg": "Fruit & Vegetables",
    "Health & Body": "Health & Beauty",
    "Beer & Wine": "Beer, Wine & Cider",
    "Easter": "Snacks & Confectionery",
    # Pass-through departments (name matches our canonical category exactly)
    "Pantry": "Pantry",
    "Frozen": "Frozen",
    "Drinks": "Drinks",
    "Bakery": "Bakery",
    "Household": "Household",
    "Baby & Child": "Baby & Child",
    "Pet": "Pet",
}

# ---------------------------------------------------------------------------
# Stage 2: Per-category keyword → subcategory rules
#
# Each entry is a list of (compiled_regex, subcategory, override_category).
# Rules are evaluated in order; first match wins.  When *override_category*
# is not None the product is re-assigned to a different parent category
# (e.g. "biscuits" in Pantry → Snacks & Confectionery).
# ---------------------------------------------------------------------------

_Rule = tuple[re.Pattern[str], str, Optional[str]]


def _rules(specs: list[tuple[str, str] | tuple[str, str, str]]) -> list[_Rule]:
    """Build compiled rule list from (pattern, subcategory[, override]) tuples."""
    out: list[_Rule] = []
    for spec in specs:
        pattern, subcategory = spec[0], spec[1]
        override = spec[2] if len(spec) == 3 else None  # type: ignore[misc]
        out.append((re.compile(pattern, re.IGNORECASE), subcategory, override))
    return out


SUBCATEGORY_RULES: dict[str, list[_Rule]] = {
    "Chilled, Dairy & Eggs": _rules([
        (r"milk", "Milk"),
        (r"cheese", "Cheese"),
        (r"yoghurt|yogurt", "Yoghurt"),
        (r"butter|spread", "Butter & Margarine"),
        (r"cream", "Cream & Sour Cream"),
        (r"\beggs?\b", "Eggs"),
        (r"pie|quiche|sausage roll|dip|hummus", "Deli & Cooked Meats"),
    ]),
    "Pantry": _rules([
        # Snack overrides (check before generic pantry rules)
        (r"biscuit|cookie", "Biscuits", "Snacks & Confectionery"),
        (r"chip|cracker", "Chips & Crackers", "Snacks & Confectionery"),
        (r"chocolate|lolly|lollies|candy|sweet", "Chocolate", "Snacks & Confectionery"),
        (r"\bnut", "Nuts & Dried Fruit", "Snacks & Confectionery"),
        # Pantry subcategories
        (r"pasta|spaghetti|macaroni|noodle", "Pasta, Rice & Noodles"),
        (r"rice|couscous", "Pasta, Rice & Noodles"),
        (r"sauce|salsa|aioli|mayo|ketchup|mustard", "Sauces & Condiments"),
        (r"cereal|muesli|oat|porridge|granola", "Breakfast Cereals"),
        (r"\bcan\b|beans|soup|tinned", "Canned Goods"),
        (r"\boil\b|vinegar", "Oil & Vinegar"),
        (r"flour|sugar|baking", "Baking"),
        (r"spread|jam|honey|peanut butter|vegemite|marmite", "Spreads"),
    ]),
    "Bakery": _rules([
        (r"bread|toast|loaf", "Bread"),
        (r"wrap|pita|tortilla|flatbread|naan", "Wraps, Pita & Flatbread"),
        (r"\brolls?\b|\bbuns?\b", "Rolls & Buns"),
        (r"cake|muffin|donut|doughnut|croissant|scone", "Cakes & Muffins"),
    ]),
    "Drinks": _rules([
        (r"coffee", "Coffee"),
        (r"\btea\b", "Tea"),
        (r"water", "Water"),
        (r"juice", "Juice"),
        (r"energy|sports", "Energy & Sports Drinks"),
        # Fallback handled below as default subcategory
    ]),
    "Frozen": _rules([
        (r"ice cream|magnum|paddle pop|kapiti|gelato|sorbet", "Ice Cream & Desserts"),
        (r"pizza", "Frozen Pizza"),
        (r"chip|wedge|fries|french frie", "Frozen Chips & Wedges"),
        (r"fish|hoki|basa|salmon|prawn|seafood", "Frozen Meat & Seafood"),
        (r"vegetable|peas?\b|corn\b|broccoli|spinach|mixed veg", "Frozen Vegetables"),
        # Fallback handled below as default subcategory
    ]),
    "Meat & Seafood": _rules([
        (r"chicken|poultry", "Chicken"),
        (r"beef|steak|rump|scotch fillet|sirloin", "Beef & Veal"),
        (r"lamb", "Lamb"),
        (r"pork|bacon|ham", "Pork"),
        (r"mince|patty|pattie", "Mince & Patties"),
        (r"sausage|burger", "Sausages & Burgers"),
        (r"salmon|fish|prawn|mussel|crab|oyster|squid|seafood", "Seafood"),
    ]),
    "Fruit & Vegetables": _rules([
        (r"apple|banana|orange|berry|berries|fruit|grape|kiwi|mango|pear|plum|melon|avocado|lemon|lime", "Fruit"),
        (r"lettuce|carrot|potato|onion|vegetable|broccoli|tomato|capsicum|cucumber|courgette|zucchini|kumara|pumpkin|spinach|celery|mushroom|corn\b|cabbage|cauliflower|garlic|ginger|bean|pea\b", "Vegetables"),
        (r"salad", "Salad"),
    ]),
    "Household": _rules([
        (r"laundry|washing powder|washing liquid|fabric soft", "Laundry"),
        (r"toilet paper|tissue|facial tissue", "Toilet Paper & Tissues"),
        # Fallback handled below as default subcategory
    ]),
    "Pet": _rules([
        (r"\bdog\b", "Dog Food"),
        (r"\bcat\b|kitten", "Cat Food"),
    ]),
    "Baby & Child": _rules([
        (r"napp", "Nappies"),
        # Fallback handled below as default subcategory
    ]),
    "Snacks & Confectionery": _rules([
        (r"chip|cracker|pretzel|popcorn", "Chips & Crackers"),
        (r"chocolate|easter egg|cadbury|whittaker", "Chocolate"),
        (r"biscuit|cookie", "Biscuits"),
        (r"\bnut", "Nuts & Dried Fruit"),
        (r"lolly|lollies|candy|gummy|jelly bean|marshmallow", "Lollies"),
    ]),
    "Beer, Wine & Cider": _rules([
        # No subcategory rules defined in CATEGORY_HIERARCHY for alcohol
    ]),
    "Health & Beauty": _rules([
        # No subcategory rules defined in CATEGORY_HIERARCHY for health
    ]),
}

# Default subcategories when no keyword rule matches
_DEFAULT_SUBCATEGORY: dict[str, str] = {
    "Drinks": "Soft Drinks",
    "Frozen": "Frozen Meals",
    "Household": "Cleaning",
    "Baby & Child": "Baby Food",
}


def classify_product(
    department: str | None,
    name: str,
) -> tuple[str | None, str | None]:
    """Classify a product into (category, subcategory).

    Parameters
    ----------
    department:
        The Woolworths ``department`` value (e.g. "Fridge & Deli").
    name:
        The full product name used for keyword matching.

    Returns
    -------
    tuple of (category, subcategory), either of which may be ``None``
    if no match is found.
    """
    if not name:
        return None, None

    # Stage 1: department → category
    category: str | None = None
    if department:
        category = DEPARTMENT_TO_CATEGORY.get(department)
        # "Back to School" and unknown departments: fall through to name-based

    # If department didn't map, try matching name against all rule sets
    if category is None:
        category = _category_from_name(name)

    if category is None:
        return None, None

    # Stage 2: name keywords → subcategory
    subcategory: str | None = None
    rules = SUBCATEGORY_RULES.get(category, [])
    for pattern, subcat, override_cat in rules:
        if pattern.search(name):
            if override_cat:
                return override_cat, subcat
            subcategory = subcat
            break

    if subcategory is None:
        subcategory = _DEFAULT_SUBCATEGORY.get(category)

    return category, subcategory


def _category_from_name(name: str) -> str | None:
    """Try to infer category purely from product name keywords."""
    name_lower = name.lower()
    # Check each category's rules against the name
    for category, rules in SUBCATEGORY_RULES.items():
        for pattern, _, __ in rules:
            if pattern.search(name_lower):
                return category
    return None


__all__ = ["classify_product"]
