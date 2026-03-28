"""Product normalization utilities for cross-chain matching.

Parses freeform size strings into structured numeric fields, normalizes
brand names, and cleans product names for similarity comparison.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Size parsing
# ---------------------------------------------------------------------------

@dataclass
class StructuredSize:
    volume_ml: Optional[float] = None
    weight_g: Optional[float] = None
    pack_count: Optional[int] = None
    unit_volume_ml: Optional[float] = None
    unit_weight_g: Optional[float] = None
    size_type: str = "unknown"  # volume, weight, count, each, unknown
    raw: str = ""


# Conversion factors to base units (ml for volume, g for weight)
_VOLUME_FACTORS: dict[str, float] = {
    "ml": 1.0,
    "cl": 10.0,
    "l": 1000.0,
    "ltr": 1000.0,
    "litre": 1000.0,
    "litres": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
}

_WEIGHT_FACTORS: dict[str, float] = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
}

_ALL_VOLUME_UNITS = "|".join(sorted(_VOLUME_FACTORS.keys(), key=len, reverse=True))
_ALL_WEIGHT_UNITS = "|".join(sorted(_WEIGHT_FACTORS.keys(), key=len, reverse=True))
_ALL_UNITS = "|".join(
    sorted(
        list(_VOLUME_FACTORS.keys()) + list(_WEIGHT_FACTORS.keys()),
        key=len,
        reverse=True,
    )
)

# Pattern 1: multipack with unit size — "6 x 330ml", "4x250g", "12 X 355 ML"
_MULTI_RE = re.compile(
    rf"(\d+)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*({_ALL_UNITS})\b",
    re.IGNORECASE,
)

# Pattern 2: pack count then size elsewhere — "6 Pack 330ml Cans", "12pk 500ml"
_PACK_SIZE_RE = re.compile(
    rf"(\d+)\s*(?:pk|pack)\b.*?(\d+(?:\.\d+)?)\s*({_ALL_UNITS})\b",
    re.IGNORECASE,
)

# Pattern 3: weight range — "1kg-1.5kg", "500g - 700g"
_RANGE_RE = re.compile(
    rf"(\d+(?:\.\d+)?)\s*({_ALL_UNITS})\s*-\s*(\d+(?:\.\d+)?)\s*({_ALL_UNITS})\b",
    re.IGNORECASE,
)

# Pattern 4: simple size — "500g", "1.5L", "750ml"
_SIMPLE_RE = re.compile(
    rf"(\d+(?:\.\d+)?)\s*({_ALL_UNITS})\b",
    re.IGNORECASE,
)

# Pattern 5: pack count only — "6 Pack", "12pk"
_PACK_ONLY_RE = re.compile(
    r"(\d+)\s*(?:pk|pack)\b",
    re.IGNORECASE,
)

# Pattern 6: per-unit — "each", "ea"
_EACH_RE = re.compile(r"\b(?:each|ea)\b", re.IGNORECASE)

# Size extraction from noisy text — matches the size portion of strings like
# "Original Crunchy 375g" or "6 x 330ml Cans"
_SIZE_EXTRACT_RE = re.compile(
    rf"(?:\d+\s*[xX×]\s*)?\d+(?:\.\d+)?\s*(?:{_ALL_UNITS})\b"
    rf"|\d+\s*(?:pk|pack)\b",
    re.IGNORECASE,
)


def _to_ml(value: float, unit: str) -> Optional[float]:
    factor = _VOLUME_FACTORS.get(unit.lower())
    return round(value * factor, 2) if factor is not None else None


def _to_g(value: float, unit: str) -> Optional[float]:
    factor = _WEIGHT_FACTORS.get(unit.lower())
    return round(value * factor, 2) if factor is not None else None


def _is_volume_unit(unit: str) -> bool:
    return unit.lower() in _VOLUME_FACTORS


def _is_weight_unit(unit: str) -> bool:
    return unit.lower() in _WEIGHT_FACTORS


def parse_structured_size(text: str) -> StructuredSize:
    """Parse a freeform size string into structured numeric fields.

    Handles multipacks ("6 x 330ml"), simple sizes ("500g", "1.5L"),
    weight ranges ("1kg-1.5kg"), pack counts ("6 Pack"), and per-unit ("each").
    """
    if not text:
        return StructuredSize(raw="")

    text = text.strip()
    result = StructuredSize(raw=text)

    # Pattern 1: multipack — "6 x 330ml"
    m = _MULTI_RE.search(text)
    if m:
        count = int(m.group(1))
        unit_val = float(m.group(2))
        unit = m.group(3)
        result.pack_count = count
        if _is_volume_unit(unit):
            result.unit_volume_ml = _to_ml(unit_val, unit)
            result.volume_ml = round(result.unit_volume_ml * count, 2)
            result.size_type = "volume"
        elif _is_weight_unit(unit):
            result.unit_weight_g = _to_g(unit_val, unit)
            result.weight_g = round(result.unit_weight_g * count, 2)
            result.size_type = "weight"
        return result

    # Pattern 2: pack + size elsewhere — "6 Pack 330ml Cans"
    m = _PACK_SIZE_RE.search(text)
    if m:
        count = int(m.group(1))
        unit_val = float(m.group(2))
        unit = m.group(3)
        result.pack_count = count
        if _is_volume_unit(unit):
            result.unit_volume_ml = _to_ml(unit_val, unit)
            result.volume_ml = round(result.unit_volume_ml * count, 2)
            result.size_type = "volume"
        elif _is_weight_unit(unit):
            result.unit_weight_g = _to_g(unit_val, unit)
            result.weight_g = round(result.unit_weight_g * count, 2)
            result.size_type = "weight"
        return result

    # Pattern 3: weight/volume range — "1kg-1.5kg"
    m = _RANGE_RE.search(text)
    if m:
        low_val = float(m.group(1))
        low_unit = m.group(2)
        high_val = float(m.group(3))
        high_unit = m.group(4)
        mid = (low_val + high_val) / 2
        # Use the first unit for conversion (they should match)
        if _is_weight_unit(low_unit):
            result.weight_g = _to_g(mid, low_unit)
            result.size_type = "weight"
        elif _is_volume_unit(low_unit):
            result.volume_ml = _to_ml(mid, low_unit)
            result.size_type = "volume"
        return result

    # Pattern 4: simple size — "500g", "1.5L"
    m = _SIMPLE_RE.search(text)
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if _is_volume_unit(unit):
            result.volume_ml = _to_ml(val, unit)
            result.size_type = "volume"
        elif _is_weight_unit(unit):
            result.weight_g = _to_g(val, unit)
            result.size_type = "weight"
        return result

    # Pattern 5: pack count only — "6 Pack"
    m = _PACK_ONLY_RE.search(text)
    if m:
        result.pack_count = int(m.group(1))
        result.size_type = "count"
        return result

    # Pattern 6: per-unit
    if _EACH_RE.search(text):
        result.size_type = "each"
        return result

    return result


def extract_size_from_text(text: str) -> Optional[str]:
    """Extract the size substring from noisy text.

    "Original Crunchy 375g" → "375g"
    "6 x 330ml Cans" → "6 x 330ml"
    "Smooth 500g Jar" → "500g"
    """
    if not text:
        return None
    m = _SIZE_EXTRACT_RE.search(text)
    return m.group(0).strip() if m else None


def sizes_equivalent(
    a: StructuredSize,
    b: StructuredSize,
    tolerance: float = 0.02,
) -> Optional[bool]:
    """Compare two structured sizes numerically.

    Returns True if equivalent within tolerance, False if clearly different,
    None if insufficient data to decide.
    """
    # Both have volume
    if a.volume_ml is not None and b.volume_ml is not None:
        if a.volume_ml == 0 and b.volume_ml == 0:
            return True
        if a.volume_ml == 0 or b.volume_ml == 0:
            return False
        ratio = abs(a.volume_ml - b.volume_ml) / max(a.volume_ml, b.volume_ml)
        return ratio <= tolerance

    # Both have weight
    if a.weight_g is not None and b.weight_g is not None:
        if a.weight_g == 0 and b.weight_g == 0:
            return True
        if a.weight_g == 0 or b.weight_g == 0:
            return False
        ratio = abs(a.weight_g - b.weight_g) / max(a.weight_g, b.weight_g)
        return ratio <= tolerance

    # Both are pack-count only (no volume/weight)
    if (
        a.size_type == "count"
        and b.size_type == "count"
        and a.pack_count is not None
        and b.pack_count is not None
    ):
        return a.pack_count == b.pack_count

    # Both are per-unit
    if a.size_type == "each" and b.size_type == "each":
        return True

    # One has volume/weight, the other doesn't — can't compare
    return None


# ---------------------------------------------------------------------------
# Brand normalization
# ---------------------------------------------------------------------------

# Own-brand equivalence groups. Each set contains brand names (lowercase)
# that are considered interchangeable store brands.
OWN_BRAND_GROUPS: list[set[str]] = [
    {"woolworths", "countdown", "woolworths homebrand"},
    {"pams", "pams finest"},
    {"budget"},
    {"value"},
]

# Map: lowercase brand → group index for fast lookup
_BRAND_TO_GROUP: dict[str, int] = {}
for _idx, _group in enumerate(OWN_BRAND_GROUPS):
    for _brand in _group:
        _BRAND_TO_GROUP[_brand] = _idx


def normalize_brand(brand: str) -> str:
    """Lowercase and strip whitespace from a brand name."""
    return brand.strip().lower()


def brands_equivalent(
    brand_a: Optional[str],
    brand_b: Optional[str],
) -> bool:
    """Check if two brands are equivalent (same brand or same own-brand group).

    Returns True if the brands match exactly (case-insensitive) or belong
    to the same own-brand group.
    """
    if not brand_a or not brand_b:
        return False

    a = normalize_brand(brand_a)
    b = normalize_brand(brand_b)

    if a == b:
        return True

    group_a = _BRAND_TO_GROUP.get(a)
    group_b = _BRAND_TO_GROUP.get(b)

    if group_a is not None and group_b is not None:
        return group_a == group_b

    return False


# ---------------------------------------------------------------------------
# Name cleaning
# ---------------------------------------------------------------------------

# Noise words to strip from product names before similarity comparison.
# These are common descriptor words that don't help distinguish products.
_NOISE_WORDS = {
    "brand", "new", "nz", "fresh", "premium", "original", "classic",
    "range", "product", "item",
}

# Size patterns to strip from names (same as matching.py _SIZE_IN_NAME_RE)
_SIZE_IN_NAME_RE = re.compile(
    r"\d+\s*[xX×]\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|cl|pk|ea)\b"
    r"|\d+(?:\.\d+)?\s*(?:g|kg|ml|l|cl|pk|ea)\b"
    r"|\d+\s*(?:pk|pack)\b",
    re.IGNORECASE,
)


def clean_product_name(name: str, brand: Optional[str] = None) -> str:
    """Clean a product name for similarity comparison.

    Strips brand (all occurrences), size patterns, noise words,
    and normalizes whitespace. Returns lowercase.
    """
    result = name.lower()

    # Strip all brand occurrences
    if brand:
        result = result.replace(brand.lower(), "")

    # Strip size patterns
    result = _SIZE_IN_NAME_RE.sub("", result)

    # Strip noise words (whole words only)
    tokens = result.split()
    tokens = [t for t in tokens if t not in _NOISE_WORDS]

    result = " ".join(tokens).strip()
    # Collapse multiple spaces
    result = re.sub(r"\s+", " ", result)
    return result


__all__ = [
    "StructuredSize",
    "parse_structured_size",
    "extract_size_from_text",
    "sizes_equivalent",
    "normalize_brand",
    "brands_equivalent",
    "clean_product_name",
    "OWN_BRAND_GROUPS",
]
