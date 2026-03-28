from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Price, Product
from app.services.normalizer import brands_equivalent as _brands_equivalent


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


# Regex pattern for embedded sizes like "500g", "2l", "6 x 500ml" etc.
_SQL_SIZE_PATTERN = r"\d+\s*x\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|pk|ea)\M|\d+(?:\.\d+)?\s*(?:g|kg|ml|l|pk|ea)\M"


def _db_name_fully_cleaned():
    """SQL expression that strips brand AND embedded size patterns from Product.name.

    Mirrors _clean_search_name() on the DB side — removes all brand occurrences
    via replace(), then strips embedded sizes like '500g' or '6 x 500ml' via
    regexp_replace(), then trims whitespace.
    """
    brand_stripped = case(
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
    size_stripped = func.regexp_replace(brand_stripped, _SQL_SIZE_PATTERN, "", "gi")
    return func.trim(func.regexp_replace(size_stripped, r"\s+", " ", "g"))


def _aliased_name_fully_cleaned(product_alias):
    """SQL expression that strips brand AND embedded sizes from an aliased Product.

    Same logic as _db_name_fully_cleaned() but operates on an aliased() model
    for use in self-joins (e.g. rankings cross-chain matching).
    """
    brand_stripped = case(
        (
            and_(product_alias.brand.is_not(None), product_alias.brand != ""),
            func.replace(
                func.lower(product_alias.name),
                func.lower(product_alias.brand),
                "",
            ),
        ),
        else_=func.lower(product_alias.name),
    )
    size_stripped = func.regexp_replace(brand_stripped, _SQL_SIZE_PATTERN, "", "gi")
    return func.trim(func.regexp_replace(size_stripped, r"\s+", " ", "g"))


def _sql_normalize_size(size_col):
    """SQL expression that normalizes a size column for comparison.

    Lowercases and replaces common unit aliases so that '500 Grams' matches '500g'.
    """
    s = func.lower(func.coalesce(size_col, ""))
    # Replace long unit names with abbreviations
    for long, short in (
        ("litres", "l"), ("litre", "l"), ("liters", "l"), ("liter", "l"),
        ("millilitres", "ml"), ("millilitre", "ml"), ("milliliters", "ml"), ("milliliter", "ml"),
        ("kilograms", "kg"), ("kilogram", "kg"),
        ("grams", "g"), ("gram", "g"),
        ("pack", "pk"),
        ("each", "ea"),
    ):
        s = func.replace(s, long, short)
    # Strip spaces between number and unit (e.g. "500 g" -> "500g")
    s = func.regexp_replace(s, r"(\d)\s+(g|kg|ml|l|pk|ea)\M", r"\1\2", "gi")
    return func.trim(s)


async def find_cross_chain_matches(
    session: AsyncSession,
    *,
    product_id: UUID,
    source_chain: str,
    product_name: str,
    product_brand: Optional[str],
    product_size: Optional[str],
    product_department: Optional[str] = None,
    product_subcategory: Optional[str] = None,
    source_embedding: Optional[list] = None,
    target_chains: list[str],
    store_ids: list[UUID],
    product_volume_ml: Optional[float] = None,
    product_weight_g: Optional[float] = None,
    product_pack_count: Optional[int] = None,
) -> dict[str, list[dict]]:
    """Find best matching products in target chains using pg_trgm similarity.

    Strips brand from both sides so similarity focuses on the product type,
    then boosts same-brand matches to prefer the exact same product.
    When source_embedding is provided, blends vector similarity with trigram.
    When structured size fields are available, uses numeric comparison as a
    hard filter instead of string-based size matching.

    Returns dict mapping chain -> list of candidate matches (up to 3 per chain),
    each with keys: product_id, name, brand, size, similarity.
    """
    if not target_chains or not store_ids:
        return {}

    # Strip brand + embedded sizes from search name (mirrors DB-side cleaning)
    search_name = _clean_search_name(product_name, product_brand)
    norm_size = normalize_size(product_size)

    # Similarity on cleaned name only — no size dilution
    db_name_clean = _db_name_fully_cleaned()
    sim = func.similarity(db_name_clean, search_name)

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
        sim >= 0.2,
        has_price_in_stores,
    ]

    # --- Structured size filter ---
    # When the source product has numeric size data, require candidates to
    # match within 2% tolerance OR have NULL structured fields (un-backfilled).
    TOLERANCE = 0.02
    has_structured_size = product_volume_ml is not None or product_weight_g is not None

    if product_volume_ml is not None:
        conditions.append(or_(
            Product.volume_ml.is_(None),  # allow un-backfilled rows through
            func.abs(Product.volume_ml - product_volume_ml) / func.greatest(product_volume_ml, 0.01) <= TOLERANCE,
        ))
    if product_weight_g is not None:
        conditions.append(or_(
            Product.weight_g.is_(None),  # allow un-backfilled rows through
            func.abs(Product.weight_g - product_weight_g) / func.greatest(product_weight_g, 0.01) <= TOLERANCE,
        ))
    if product_pack_count is not None:
        conditions.append(or_(
            Product.pack_count.is_(None),
            Product.pack_count == product_pack_count,
        ))

    # Size boost: only used as fallback when structured data is not available
    size_boost = 0.0
    if not has_structured_size and norm_size:
        db_norm_size = _sql_normalize_size(Product.size)
        size_boost = case(
            (db_norm_size == norm_size, 0.15),  # exact normalized match
            (func.strpos(db_norm_size, norm_size) > 0, 0.1),  # substring (multipack)
            else_=0.0,
        )

    # Department match/mismatch scoring (not a hard filter — departments may be NULL)
    dept_boost = 0.0
    if product_department:
        dept_boost = case(
            (Product.department == product_department, 0.4),
            (Product.department.is_(None), 0.0),
            else_=-0.15,  # penalty for different department
        )

    # Subcategory boost — tighter product type matching when available
    subcat_boost = 0.0
    if product_subcategory:
        subcat_boost = case(
            (
                func.lower(func.coalesce(Product.subcategory, "")) == product_subcategory.lower(),
                0.25,
            ),
            else_=0.0,
        )

    # Brand boost — supports own-brand equivalence via normalized_brand
    brand_boost = 0.0
    if product_brand:
        from app.services.normalizer import normalize_brand, OWN_BRAND_GROUPS, _BRAND_TO_GROUP

        norm_src_brand = normalize_brand(product_brand)
        src_group = _BRAND_TO_GROUP.get(norm_src_brand)

        if src_group is not None:
            # Source is an own-brand — match any brand in the same group
            group_brands = list(OWN_BRAND_GROUPS[src_group])
            brand_boost = case(
                (
                    func.lower(func.coalesce(Product.normalized_brand, "")).in_(group_brands),
                    0.15,
                ),
                (
                    and_(
                        Product.brand.is_not(None),
                        func.lower(Product.brand) == norm_src_brand,
                    ),
                    0.15,
                ),
                else_=0.0,
            )
        else:
            # Regular brand — exact match
            brand_boost = case(
                (
                    and_(
                        Product.brand.is_not(None),
                        func.lower(Product.brand) == norm_src_brand,
                    ),
                    0.15,
                ),
                else_=0.0,
            )

    # When source embedding is available, blend vector similarity with trigram
    if source_embedding is not None and hasattr(Product, "embedding"):
        vector_sim = (1 - Product.embedding.cosine_distance(source_embedding))
        score = (vector_sim * 0.5 + sim * 0.2 + dept_boost + subcat_boost + brand_boost + size_boost).label("score")
    else:
        score = (sim + dept_boost + subcat_boost + brand_boost + size_boost).label("score")

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
    source_embedding: Optional[list] = None,
    source_product_id: Optional[UUID] = None,
    store_id: UUID,
    limit: int = 3,
    product_volume_ml: Optional[float] = None,
    product_weight_g: Optional[float] = None,
    product_pack_count: Optional[int] = None,
) -> list[dict]:
    """Find similar products at a specific store, focused on product type.

    Key design choices:
    - Strips brand from BOTH sides (all occurrences) so "woolworths spaghetti"
      matches "pams spaghetti" purely on "spaghetti".
    - Matches on product name only (no size in similarity text).
    - Department and subcategory are BOOSTS, not hard filters, because
      different chains may have NULL or differently-named departments.
    - Size is a boost to prefer same-size alternatives (or hard filter when
      structured data is available).

    Returns list of candidates with keys: product_id, name, brand, size,
    image_url, price_nzd, promo_price_nzd, similarity.
    """
    # Strip ALL brand occurrences + size patterns from search name
    search_name = _clean_search_name(product_name, product_brand)

    # Strip ALL brand occurrences + embedded sizes from DB-side names
    db_name_clean = _db_name_fully_cleaned()

    # Similarity on cleaned name only (no size) — focuses on product type
    sim = func.similarity(db_name_clean, search_name)

    conditions = [
        Price.store_id == store_id,
        sim >= 0.1,
    ]

    # Exclude the source product itself
    if source_product_id:
        conditions.append(Product.id != source_product_id)

    # Department match/mismatch scoring (NOT a hard filter — PAK'nSAVE has NULL departments)
    dept_boost = 0.0
    if product_department:
        dept_boost = case(
            (Product.department == product_department, 0.3),
            (Product.department.is_(None), 0.0),
            else_=-0.15,  # penalty for different department
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

    # Size: use structured numeric comparison when available, string fallback otherwise
    size_boost = 0.0
    has_structured_size = product_volume_ml is not None or product_weight_g is not None

    if has_structured_size:
        # Boost same-size products using numeric comparison
        TOLERANCE = 0.02
        if product_volume_ml is not None:
            size_boost = case(
                (Product.volume_ml.is_(None), 0.0),
                (
                    func.abs(Product.volume_ml - product_volume_ml) / func.greatest(product_volume_ml, 0.01) <= TOLERANCE,
                    0.15,
                ),
                else_=0.0,
            )
        elif product_weight_g is not None:
            size_boost = case(
                (Product.weight_g.is_(None), 0.0),
                (
                    func.abs(Product.weight_g - product_weight_g) / func.greatest(product_weight_g, 0.01) <= TOLERANCE,
                    0.15,
                ),
                else_=0.0,
            )
    else:
        norm_size = normalize_size(product_size)
        if norm_size:
            size_boost = case(
                (func.strpos(func.lower(func.coalesce(Product.size, "")), norm_size) > 0, 0.1),
                else_=0.0,
            )

    # When source embedding is available, blend vector similarity with trigram
    if source_embedding is not None and hasattr(Product, "embedding"):
        vector_sim = (1 - Product.embedding.cosine_distance(source_embedding))
        score = (vector_sim * 0.5 + sim * 0.2 + dept_boost + subcat_boost + size_boost).label("score")
    else:
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


__all__ = [
    "normalize_size",
    "find_cross_chain_matches",
    "find_store_suggestions",
    "_clean_search_name",
    "_aliased_name_fully_cleaned",
    "_sql_normalize_size",
]
