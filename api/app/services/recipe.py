from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from geoalchemy2 import Geography

from app.db.models import Price, Product, Recipe, RecipeIngredient, Store
from app.services.matching import _db_name_fully_cleaned
from app.services.trolley import _effective_price


# --- Ingredient parsing ---

_INGREDIENT_RE = re.compile(
    r"^(\d+(?:\.\d+)?)\s*"
    r"(cups?|tbsp|tsp|ml|l|g|kg|cloves?|slices?|pieces?|stalks?|sprigs?|bunch(?:es)?|cans?|tins?|packets?|rashers?)?\s*"
    r"(?:of\s+)?"
    r"(.+)$",
    re.IGNORECASE,
)


def parse_ingredient(description: str) -> dict:
    """Extract quantity, unit, and display_name from freeform ingredient text.

    Examples:
        "500g chicken breast"  -> {quantity: 500, unit: "g", display_name: "chicken breast"}
        "2 cloves garlic"      -> {quantity: 2, unit: "cloves", display_name: "garlic"}
        "salt and pepper"      -> {quantity: None, unit: None, display_name: "salt and pepper"}
    """
    text = description.strip()
    m = _INGREDIENT_RE.match(text)
    if m:
        qty_str, unit, name = m.groups()
        return {
            "quantity": float(qty_str),
            "unit": unit.lower().rstrip("s") if unit else None,
            "display_name": name.strip(),
        }
    return {"quantity": None, "unit": None, "display_name": text.lower()}


# --- Ingredient matching ---

async def find_ingredient_matches(
    session: AsyncSession,
    display_name: str,
    store_ids: list[UUID],
) -> dict[UUID, dict]:
    """Find best matching product for an ingredient at each store.

    Returns dict mapping store_id -> {product_id, name, image_url, price}.
    Uses pg_trgm similarity on brand-stripped product names.
    """
    if not store_ids:
        return {}

    search_name = display_name.lower().strip()
    db_name_clean = _db_name_fully_cleaned()
    sim = func.similarity(db_name_clean, search_name)

    # Find products with prices at the given stores, ranked by similarity
    query = (
        select(
            Product.id,
            Product.name,
            Product.image_url,
            Price.price_nzd,
            Price.promo_price_nzd,
            Price.promo_ends_at,
            Price.store_id,
            sim.label("sim"),
        )
        .join(Price, Price.product_id == Product.id)
        .where(
            and_(
                Price.store_id.in_(store_ids),
                sim >= 0.15,
            )
        )
        .order_by(sim.desc())
    )

    result = await session.execute(query)
    rows = result.all()

    # Pick best match per store
    matches: dict[UUID, dict] = {}
    for pid, name, image_url, price_nzd, promo_price_nzd, promo_ends_at, store_id, similarity in rows:
        if store_id in matches:
            continue
        eff_price = _effective_price(price_nzd, promo_price_nzd, promo_ends_at)
        matches[store_id] = {
            "product_id": pid,
            "name": name,
            "image_url": image_url,
            "price": eff_price,
        }

    return matches


# --- Cost comparison orchestrator ---

async def compare_recipe_cost(
    session: AsyncSession,
    *,
    recipe_id: UUID,
    lat: float,
    lon: float,
    radius_km: float,
) -> Optional[dict]:
    """Compare recipe ingredient costs across nearby stores."""

    # 1. Load recipe with ingredients
    recipe_query = (
        select(Recipe)
        .options(selectinload(Recipe.ingredients))
        .where(Recipe.id == recipe_id)
    )
    recipe_result = await session.execute(recipe_query)
    recipe = recipe_result.scalar_one_or_none()
    if not recipe:
        return None

    # 2. Find nearby stores (same PostGIS pattern as trolley)
    user_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    user_point_geog = cast(user_point, Geography)
    radius_m = radius_km * 1000

    distance_m = func.ST_Distance(Store.geog, user_point_geog).label("distance_m")
    store_query = (
        select(Store, distance_m)
        .where(Store.geog.is_not(None))
        .where(func.ST_DWithin(Store.geog, user_point_geog, radius_m))
        .order_by(distance_m)
    )
    store_result = await session.execute(store_query)
    nearby_stores = [(store, dist) for store, dist in store_result.all()]

    if not nearby_stores:
        return {
            "recipe": _recipe_summary(recipe),
            "stores": [],
            "summary": {"total_ingredients": len(recipe.ingredients), "total_stores": 0, "complete_stores": 0},
        }

    store_map: dict[UUID, tuple[Store, float]] = {}
    store_ids: list[UUID] = []
    for store, dist in nearby_stores:
        store_map[store.id] = (store, dist)
        store_ids.append(store.id)

    # 3. For each ingredient, find best match at each store
    ingredient_matches: dict[UUID, dict[UUID, dict]] = {}
    for ingredient in recipe.ingredients:
        matches = await find_ingredient_matches(session, ingredient.display_name, store_ids)
        ingredient_matches[ingredient.id] = matches

    # 4. Build per-store breakdowns
    store_breakdowns = []
    for store_id, (store, distance) in store_map.items():
        ingredient_items = []
        estimated_total = 0.0
        items_available = 0

        for ingredient in recipe.ingredients:
            match = ingredient_matches.get(ingredient.id, {}).get(store_id)
            if match:
                items_available += 1
                estimated_total += match["price"]
                ingredient_items.append({
                    "ingredient_id": str(ingredient.id),
                    "ingredient_description": ingredient.description,
                    "display_name": ingredient.display_name,
                    "optional": ingredient.optional,
                    "available": True,
                    "matched_product_id": str(match["product_id"]),
                    "matched_product_name": match["name"],
                    "matched_product_image": match["image_url"],
                    "price": match["price"],
                    "quantity": ingredient.quantity,
                    "unit": ingredient.unit,
                })
            else:
                ingredient_items.append({
                    "ingredient_id": str(ingredient.id),
                    "ingredient_description": ingredient.description,
                    "display_name": ingredient.display_name,
                    "optional": ingredient.optional,
                    "available": False,
                    "matched_product_id": None,
                    "matched_product_name": None,
                    "matched_product_image": None,
                    "price": None,
                    "quantity": ingredient.quantity,
                    "unit": ingredient.unit,
                })

        items_total = len(recipe.ingredients)
        store_breakdowns.append({
            "store_id": str(store_id),
            "store_name": store.name,
            "chain": store.chain,
            "distance_km": round(distance / 1000, 2),
            "estimated_total": round(estimated_total, 2),
            "items_available": items_available,
            "items_total": items_total,
            "is_complete": items_available == items_total,
            "ingredients": ingredient_items,
        })

    # Sort: complete stores first, then by estimated total
    store_breakdowns.sort(key=lambda s: (not s["is_complete"], s["estimated_total"]))

    return {
        "recipe": _recipe_summary(recipe),
        "stores": store_breakdowns,
        "summary": {
            "total_ingredients": len(recipe.ingredients),
            "total_stores": len(store_breakdowns),
            "complete_stores": sum(1 for s in store_breakdowns if s["is_complete"]),
        },
    }


def _recipe_summary(recipe: Recipe) -> dict:
    return {
        "id": str(recipe.id),
        "title": recipe.title,
        "description": recipe.description,
        "servings": recipe.servings,
        "image_url": recipe.image_url,
        "ingredient_count": len(recipe.ingredients),
    }


# --- CRUD ---

async def create_recipe(
    session: AsyncSession,
    *,
    title: str,
    description: Optional[str],
    servings: int,
    image_url: Optional[str] = None,
    source_url: Optional[str] = None,
    created_by: Optional[str] = None,
    ingredients: list[dict],
) -> Recipe:
    recipe = Recipe(
        title=title,
        description=description,
        servings=servings,
        image_url=image_url,
        source_url=source_url,
        created_by=created_by,
        is_public=True,
        is_seeded=False,
    )
    session.add(recipe)
    await session.flush()

    for ing_data in ingredients:
        parsed = parse_ingredient(ing_data["description"])
        ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            description=ing_data["description"],
            quantity=ing_data.get("quantity") or parsed["quantity"],
            unit=ing_data.get("unit") or parsed["unit"],
            display_name=ing_data.get("display_name") or parsed["display_name"],
            optional=ing_data.get("optional", False),
        )
        session.add(ingredient)

    await session.commit()
    # Reload with ingredients
    await session.refresh(recipe, ["ingredients"])
    return recipe


async def get_recipe(session: AsyncSession, recipe_id: UUID) -> Optional[Recipe]:
    query = (
        select(Recipe)
        .options(selectinload(Recipe.ingredients))
        .where(Recipe.id == recipe_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_recipes(
    session: AsyncSession,
    *,
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    base = select(Recipe).where(Recipe.is_public == True)
    if q:
        base = base.where(Recipe.title.ilike(f"%{q}%"))

    # Count
    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Fetch with ingredient counts
    query = (
        base
        .options(selectinload(Recipe.ingredients))
        .order_by(Recipe.is_seeded.desc(), Recipe.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    recipes = result.scalars().all()

    items = [
        {
            "id": str(r.id),
            "title": r.title,
            "description": r.description,
            "servings": r.servings,
            "image_url": r.image_url,
            "ingredient_count": len(r.ingredients),
        }
        for r in recipes
    ]

    return {"items": items, "total": total}


async def delete_recipe(session: AsyncSession, recipe_id: UUID, creator_id: str) -> bool:
    recipe = await get_recipe(session, recipe_id)
    if not recipe:
        return False
    if recipe.is_seeded:
        return False
    if recipe.created_by != creator_id:
        return False
    await session.delete(recipe)
    await session.commit()
    return True


__all__ = [
    "parse_ingredient",
    "find_ingredient_matches",
    "compare_recipe_cost",
    "create_recipe",
    "get_recipe",
    "list_recipes",
    "delete_recipe",
]
