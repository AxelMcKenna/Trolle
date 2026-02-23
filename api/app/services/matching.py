from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, case, func, select
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

_SIZE_IN_NAME_RE = re.compile(
    r"\d+\s*x\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|pk|ea)\b"
    r"|\d+(?:\.\d+)?\s*(?:g|kg|ml|l|pk|ea)\b",
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
    raw = m.group(1)
    number = str(float(raw)).rstrip("0").rstrip(".")
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
        stripped = name[len(brand):].lstrip(" -\u2013")
        return stripped if stripped else name
    return name


def _clean_search_name(name: str, brand: Optional[str]) -> str:
    """Extract the core product description from a name.

    Removes ALL occurrences of the brand and any size patterns embedded in
    the name, leaving just the product-type keywords.

    Example: "woolworths spaghetti woolworths pasta spaghetti" with brand
    "woolworths" -> "spaghetti pasta spaghetti"
    """
    result = name.lower()
    if brand:
        result = result.replace(brand.lower(), "")
    result = _SIZE_IN_NAME_RE.sub("", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def _db_name_cleaned():
    """SQL expression that removes ALL occurrences of brand from Product.name.

    Uses replace() instead of substr() so brand names appearing anywhere in
    the product name are removed (e.g. "woolworths spaghetti woolworths pasta
    spaghetti" -> " spaghetti  pasta spaghetti").
    """
    return func.trim(
        case(
            (
                and_(Product.brand.is_not(None), Product.brand != ""),
                func.replace(
                    func.lower(Product.name),
                    func.lower(Product.brand),
                    "",
                ),
            ),
            else_=func.lower(Product.name),
        )
    )


async def find_cross_chain_matches(
    session: AsyncSession,
    *,
    product_id: UUID,
    source_chain: str,
    product_name: str,
    product_brand: Optional[str],
    product_size: Optional[str],
    product_department: Optional[str] = None,
    target_chains: list[str],
    store_ids: list[UUID],
) -> dict[str, list[dict]]:
    """Find best matching products in target chains using pg_trgm similarity.

    Strips brand from both sides so similarity focuses on the product type,
    then boosts same-brand matches to prefer the exact same product.

    Returns dict mapping chain -> list of candidate matches (up to 3 per chain),
    each with keys: product_id, name, brand, size, similarity.
    """
    if not target_chains or not store_ids:
        return {}

    # Strip brand from search name
    search_name = _strip_brand_prefix(product_name, product_brand)
    norm_size = normalize_size(product_size)
    search_text = f"{search_name} {norm_size}".strip().lower()

    # Strip brand from DB-side product names too
    db_name_clean = _db_name_cleaned()
    db_text = func.concat(db_name_clean, " ", func.lower(func.coalesce(Product.size, "")))
    sim = func.similarity(db_text, search_text)

    # Only match products that have prices in nearby stores
    has_price_in_stores = (
        select(Price.id)
        .where(Price.product_id == Product.id)
        .where(Price.store_id.in_(store_ids))
        .exists()
    )

    conditions = [
        Product.chain.in_(target_chains),
        Product.id != product_id,
        sim >= 0.25,
        has_price_in_stores,
    ]

    # Department boost (not a hard filter — departments may be NULL across chains)
    dept_boost = 0.0
    if product_department:
        dept_boost = case(
            (Product.department == product_department, 0.2),
            else_=0.0,
        )

    # Boost same-brand matches — prefer exact same product across chains
    brand_boost = 0.0
    if product_brand:
        brand_boost = case(
            (
                and_(
                    Product.brand.is_not(None),
                    func.lower(Product.brand) == product_brand.lower(),
                ),
                0.15,
            ),
            else_=0.0,
        )

    score = (sim + dept_boost + brand_boost).label("score")

    query = (
        select(
            Product.id,
            Product.name,
            Product.brand,
            Product.size,
            Product.chain,
            score,
        )
        .where(and_(*conditions))
        .order_by(score.desc())
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


async def find_store_suggestions(
    session: AsyncSession,
    *,
    product_name: str,
    product_brand: Optional[str],
    product_size: Optional[str],
    product_department: Optional[str] = None,
    product_subcategory: Optional[str] = None,
    source_product_id: Optional[UUID] = None,
    store_id: UUID,
    limit: int = 3,
) -> list[dict]:
    """Find similar products at a specific store, focused on product type.

    Key design choices:
    - Strips brand from BOTH sides (all occurrences) so "woolworths spaghetti"
      matches "pams spaghetti" purely on "spaghetti".
    - Matches on product name only (no size in similarity text).
    - Department and subcategory are BOOSTS, not hard filters, because
      different chains may have NULL or differently-named departments.
    - Size is a boost to prefer same-size alternatives.

    Returns list of candidates with keys: product_id, name, brand, size,
    image_url, price_nzd, promo_price_nzd, similarity.
    """
    # Strip ALL brand occurrences + size patterns from search name
    search_name = _clean_search_name(product_name, product_brand)

    # Strip ALL brand occurrences from DB-side product names
    db_name_clean = _db_name_cleaned()

    # Similarity on cleaned name only (no size) — focuses on product type
    sim = func.similarity(db_name_clean, search_name)

    conditions = [
        Price.store_id == store_id,
        sim >= 0.1,
    ]

    # Exclude the source product itself
    if source_product_id:
        conditions.append(Product.id != source_product_id)

    # Department boost (NOT a hard filter — PAK'nSAVE has NULL departments)
    dept_boost = 0.0
    if product_department:
        dept_boost = case(
            (Product.department == product_department, 0.3),
            else_=0.0,
        )

    # Subcategory boost — tighter product type matching when available
    subcat_boost = 0.0
    if product_subcategory:
        subcat_boost = case(
            (
                func.lower(func.coalesce(Product.subcategory, "")) == product_subcategory.lower(),
                0.2,
            ),
            else_=0.0,
        )

    # Size preference boost — prefer same size but show different sizes too
    size_boost = 0.0
    norm_size = normalize_size(product_size)
    if norm_size:
        size_boost = case(
            (func.strpos(func.lower(func.coalesce(Product.size, "")), norm_size) > 0, 0.1),
            else_=0.0,
        )

    score = (sim + dept_boost + subcat_boost + size_boost).label("score")

    query = (
        select(
            Product.id,
            Product.name,
            Product.brand,
            Product.size,
            Product.image_url,
            Price.price_nzd,
            Price.promo_price_nzd,
            score,
        )
        .join(Price, Price.product_id == Product.id)
        .where(and_(*conditions))
        .order_by(score.desc())
        .limit(limit)
    )

    result = await session.execute(query)
    return [
        {
            "product_id": str(pid),
            "name": name,
            "brand": brand,
            "size": size,
            "image_url": image_url,
            "price_nzd": price_nzd,
            "promo_price_nzd": promo_price_nzd,
            "similarity": float(sim_score),
        }
        for pid, name, brand, size, image_url, price_nzd, promo_price_nzd, sim_score in result.all()
    ]


__all__ = ["normalize_size", "find_cross_chain_matches", "find_store_suggestions"]
