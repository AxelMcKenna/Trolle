from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Price, Product


_SIZE_ALIASES = {
    "litres": "l",
    "litre": "l",
    "liter": "l",
    "liters": "l",
    "millilitres": "ml",
    "millilitre": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "kilograms": "kg",
    "kilogram": "kg",
    "grams": "g",
    "gram": "g",
    "pack": "pk",
    "each": "ea",
}

_SIZE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(" + "|".join(_SIZE_ALIASES.keys()) + r"|l|ml|kg|g|pk|ea)\b",
    re.IGNORECASE,
)


def normalize_size(size: Optional[str]) -> str:
    """Normalize size strings for comparison: '2 Litres' -> '2l', '500 Grams' -> '500g'."""
    if not size:
        return ""
    s = size.strip().lower()
    m = _SIZE_RE.search(s)
    if not m:
        return s
    number = m.group(1).rstrip("0").rstrip(".")
    unit = m.group(2).lower()
    unit = _SIZE_ALIASES.get(unit, unit)
    return f"{number}{unit}"


def _strip_brand_prefix(name: str, brand: Optional[str]) -> str:
    """Strip brand from beginning of name to avoid double-weighting in similarity."""
    if not brand:
        return name
    lower_name = name.lower()
    lower_brand = brand.lower()
    if lower_name.startswith(lower_brand):
        stripped = name[len(brand):].lstrip(" -–")
        return stripped if stripped else name
    return name


async def find_cross_chain_matches(
    session: AsyncSession,
    *,
    product_id: UUID,
    source_chain: str,
    product_name: str,
    product_brand: Optional[str],
    product_size: Optional[str],
    target_chains: list[str],
    store_ids: list[UUID],
) -> dict[str, list[dict]]:
    """Find best matching products in target chains using pg_trgm similarity.

    Returns dict mapping chain -> list of candidate matches (up to 3 per chain),
    each with keys: product_id, name, brand, size, similarity.
    """
    if not target_chains or not store_ids:
        return {}

    search_name = _strip_brand_prefix(product_name, product_brand)
    norm_size = normalize_size(product_size)
    search_text = f"{search_name} {norm_size}".strip().lower()

    # Build similarity expression against the composite text
    product_text = func.lower(Product.name + " " + func.coalesce(Product.size, ""))
    sim = func.similarity(product_text, search_text).label("sim")

    # Only match products that have prices in nearby stores
    has_price_in_stores = (
        select(Price.id)
        .where(Price.product_id == Product.id)
        .where(Price.store_id.in_(store_ids))
        .exists()
    )

    query = (
        select(
            Product.id,
            Product.name,
            Product.brand,
            Product.size,
            Product.chain,
            sim,
        )
        .where(
            and_(
                Product.chain.in_(target_chains),
                Product.id != product_id,
                sim >= 0.3,
                has_price_in_stores,
            )
        )
        .order_by(sim.desc())
    )

    result = await session.execute(query)
    rows = result.all()

    matches: dict[str, list[dict]] = {chain: [] for chain in target_chains}
    for row in rows:
        pid, name, brand, size, chain, similarity = row
        if len(matches.get(chain, [])) >= 3:
            continue
        matches.setdefault(chain, []).append({
            "product_id": pid,
            "name": name,
            "brand": brand,
            "size": size,
            "similarity": float(similarity),
        })

    return matches


__all__ = ["normalize_size", "find_cross_chain_matches"]
