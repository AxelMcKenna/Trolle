from __future__ import annotations

import logging
import secrets
import uuid as uuid_mod
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.supabase_auth import UserContext, optional_user, require_user
from app.db.models import SavedRecipe, UserProfile
from app.db.session import get_async_session, async_transaction
from app.middleware import get_limiter
from app.schemas.recipes import (
    RecipeCreate,
    RecipeResponse,
    RecipeIngredientResponse,
    RecipeListResponse,
    RecipeCostRequest,
    RecipeCostResponse,
)
from app.services.recipe import (
    create_recipe,
    get_recipe,
    list_recipes,
    delete_recipe,
    compare_recipe_cost,
    find_ingredient_matches,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recipes", tags=["recipes"])
limiter = get_limiter()


@router.get("", response_model=RecipeListResponse)
async def recipes_list(
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RecipeListResponse:
    """List recipes with optional search."""
    async with get_async_session() as session:
        result = await list_recipes(session, q=q, limit=limit, offset=offset)
        return RecipeListResponse(**result)


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def recipe_detail(recipe_id: UUID) -> RecipeResponse:
    """Get a single recipe with ingredients."""
    async with get_async_session() as session:
        recipe = await get_recipe(session, recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return RecipeResponse(
            id=str(recipe.id),
            title=recipe.title,
            description=recipe.description,
            servings=recipe.servings,
            image_url=recipe.image_url,
            source_url=recipe.source_url,
            is_public=recipe.is_public,
            is_seeded=recipe.is_seeded,
            created_by=recipe.created_by,
            ingredients=[
                RecipeIngredientResponse(
                    id=str(ing.id),
                    description=ing.description,
                    quantity=ing.quantity,
                    unit=ing.unit,
                    display_name=ing.display_name,
                    optional=ing.optional,
                )
                for ing in recipe.ingredients
            ],
        )


@router.post("", response_model=RecipeResponse, status_code=201)
async def recipe_create(
    body: RecipeCreate,
    user: Optional[UserContext] = Depends(optional_user),
    x_creator_id: Optional[str] = Header(None),
) -> RecipeResponse:
    """Create a new recipe. Uses authenticated user ID if available, falls back to X-Creator-Id header."""
    creator_id = user.id if user else x_creator_id
    async with async_transaction() as session:
        try:
            recipe = await create_recipe(
                session,
                title=body.title,
                description=body.description,
                servings=body.servings,
                image_url=body.image_url,
                source_url=body.source_url,
                created_by=creator_id,
                ingredients=[ing.dict() for ing in body.ingredients],
            )
            return RecipeResponse(
                id=str(recipe.id),
                title=recipe.title,
                description=recipe.description,
                servings=recipe.servings,
                image_url=recipe.image_url,
                source_url=recipe.source_url,
                is_public=recipe.is_public,
                is_seeded=recipe.is_seeded,
                created_by=recipe.created_by,
                ingredients=[
                    RecipeIngredientResponse(
                        id=str(ing.id),
                        description=ing.description,
                        quantity=ing.quantity,
                        unit=ing.unit,
                        display_name=ing.display_name,
                        optional=ing.optional,
                    )
                    for ing in recipe.ingredients
                ],
            )
        except HTTPException:
            raise
        except (ValueError, TypeError) as exc:
            logger.exception("Recipe creation failed: %s", exc)
            raise HTTPException(status_code=500, detail="Recipe creation failed")


@router.delete("/{recipe_id}", status_code=204)
async def recipe_delete(
    recipe_id: UUID,
    user: Optional[UserContext] = Depends(optional_user),
    x_creator_id: Optional[str] = Header(None),
) -> None:
    """Delete a user-created recipe."""
    creator_id = user.id if user else x_creator_id
    if not creator_id:
        raise HTTPException(status_code=403, detail="Authentication required")
    async with async_transaction() as session:
        deleted = await delete_recipe(session, recipe_id, creator_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Recipe not found or not deletable")


@router.post("/compare", response_model=RecipeCostResponse)
async def recipe_compare(request: RecipeCostRequest) -> RecipeCostResponse:
    """Compare recipe ingredient costs across nearby stores."""
    async with get_async_session() as session:
        try:
            result = await compare_recipe_cost(
                session,
                recipe_id=request.recipe_id,
                lat=request.lat,
                lon=request.lon,
                radius_km=request.radius_km,
            )
            if result is None:
                raise HTTPException(status_code=404, detail="Recipe not found")
            return RecipeCostResponse(**result)
        except HTTPException:
            raise
        except Exception:
            logger.exception("Recipe comparison failed")
            raise HTTPException(status_code=500, detail="Recipe comparison failed")


# --- Recipe to Trolley ---

class RecipeToTrolleyRequest(BaseModel):
    store_id: Optional[UUID] = None
    lat: float
    lon: float
    radius_km: float = 5.0


class TrolleyItemResponse(BaseModel):
    product_id: str
    name: str
    image_url: Optional[str] = None
    price: float
    ingredient_description: str


class RecipeToTrolleyResponse(BaseModel):
    items: list[TrolleyItemResponse]
    matched: int
    total_ingredients: int


@router.post("/{recipe_id}/to-trolley", response_model=RecipeToTrolleyResponse)
async def recipe_to_trolley(
    recipe_id: UUID,
    body: RecipeToTrolleyRequest,
) -> RecipeToTrolleyResponse:
    """Get matched products for a recipe's ingredients at a store.

    When store_id is omitted, auto-selects the nearest store.
    """
    from app.db.models import Recipe, Store
    from sqlalchemy.orm import selectinload
    from sqlalchemy import cast
    from geoalchemy2 import Geography

    async with get_async_session() as session:
        recipe_result = await session.execute(
            select(Recipe)
            .options(selectinload(Recipe.ingredients))
            .where(Recipe.id == recipe_id)
        )
        recipe = recipe_result.scalar_one_or_none()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        # Auto-select nearest store when store_id not provided
        store_id = body.store_id
        if store_id is None:
            user_point = func.ST_SetSRID(func.ST_MakePoint(body.lon, body.lat), 4326)
            user_geog = cast(user_point, Geography)
            nearest = await session.execute(
                select(Store.id)
                .where(Store.geog.is_not(None))
                .where(func.ST_DWithin(Store.geog, user_geog, body.radius_km * 1000))
                .order_by(func.ST_Distance(Store.geog, user_geog))
                .limit(1)
            )
            row = nearest.scalar_one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="No stores found nearby")
            store_id = row

        items: list[TrolleyItemResponse] = []
        for ingredient in recipe.ingredients:
            matches = await find_ingredient_matches(
                session, ingredient.display_name, [store_id]
            )
            match = matches.get(store_id)
            if match:
                items.append(TrolleyItemResponse(
                    product_id=str(match["product_id"]),
                    name=match["name"],
                    image_url=match["image_url"],
                    price=match["price"],
                    ingredient_description=ingredient.description,
                ))

        return RecipeToTrolleyResponse(
            items=items,
            matched=len(items),
            total_ingredients=len(recipe.ingredients),
        )


# --- Sharing ---

class RecipeShareResponse(BaseModel):
    share_token: str
    share_url: str


@router.post("/{recipe_id}/share", response_model=RecipeShareResponse)
async def share_recipe(recipe_id: UUID) -> RecipeShareResponse:
    """Generate a share link for a recipe."""
    from app.db.models import Recipe

    async with async_transaction() as session:
        result = await session.execute(select(Recipe).where(Recipe.id == recipe_id))
        recipe = result.scalar_one_or_none()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        if not recipe.share_token:
            recipe.share_token = secrets.token_urlsafe(16)[:24]

    return RecipeShareResponse(
        share_token=recipe.share_token,
        share_url=f"/recipes/shared/{recipe.share_token}",
    )


@router.get("/shared/{share_token}", response_model=RecipeResponse)
async def get_shared_recipe(share_token: str) -> RecipeResponse:
    """Get a shared recipe by its share token. No authentication required."""
    from app.db.models import Recipe
    from sqlalchemy.orm import selectinload

    async with get_async_session() as session:
        result = await session.execute(
            select(Recipe)
            .options(selectinload(Recipe.ingredients))
            .where(Recipe.share_token == share_token)
        )
        recipe = result.scalar_one_or_none()
        if not recipe:
            raise HTTPException(status_code=404, detail="Shared recipe not found")

        return RecipeResponse(
            id=str(recipe.id),
            title=recipe.title,
            description=recipe.description,
            servings=recipe.servings,
            image_url=recipe.image_url,
            source_url=recipe.source_url,
            is_public=recipe.is_public,
            is_seeded=recipe.is_seeded,
            created_by=recipe.created_by,
            ingredients=[
                RecipeIngredientResponse(
                    id=str(ing.id),
                    description=ing.description,
                    quantity=ing.quantity,
                    unit=ing.unit,
                    display_name=ing.display_name,
                    optional=ing.optional,
                )
                for ing in recipe.ingredients
            ],
        )


# --- Saved recipes (bookmarks) ---

MAX_SAVED_RECIPES = 50


class SavedRecipeResponse(BaseModel):
    id: str
    recipe_id: str
    title: str
    description: str | None = None
    servings: int
    image_url: str | None = None
    ingredient_count: int
    saved_at: str


class SavedRecipeListResponse(BaseModel):
    recipes: list[SavedRecipeResponse]
    count: int


@router.get("/saved/list", response_model=SavedRecipeListResponse)
async def list_saved_recipes(
    user: UserContext = Depends(require_user),
) -> SavedRecipeListResponse:
    """List recipes saved by the current user."""
    from app.db.models import Recipe, RecipeIngredient

    async with get_async_session() as session:
        # Single query: join saved recipes with recipes and batch-count ingredients
        ing_count_subq = (
            select(
                RecipeIngredient.recipe_id,
                func.count().label("ing_count"),
            )
            .group_by(RecipeIngredient.recipe_id)
            .subquery()
        )

        result = await session.execute(
            select(
                SavedRecipe,
                Recipe,
                func.coalesce(ing_count_subq.c.ing_count, 0).label("ingredient_count"),
            )
            .join(Recipe, SavedRecipe.recipe_id == Recipe.id)
            .outerjoin(ing_count_subq, ing_count_subq.c.recipe_id == Recipe.id)
            .where(SavedRecipe.user_id == uuid_mod.UUID(user.id))
            .order_by(SavedRecipe.created_at.desc())
        )
        rows = result.all()

        recipes = [
            SavedRecipeResponse(
                id=str(saved.id),
                recipe_id=str(recipe.id),
                title=recipe.title,
                description=recipe.description,
                servings=recipe.servings,
                image_url=recipe.image_url,
                ingredient_count=ing_count,
                saved_at=saved.created_at.isoformat(),
            )
            for saved, recipe, ing_count in rows
        ]

    return SavedRecipeListResponse(recipes=recipes, count=len(recipes))


@router.post("/{recipe_id}/save", status_code=201)
@limiter.limit("10/minute")
async def save_recipe(
    request: Request,
    recipe_id: UUID,
    user: UserContext = Depends(require_user),
) -> dict:
    """Save/bookmark a recipe to the user's profile."""
    user_uuid = uuid_mod.UUID(user.id)

    async with async_transaction() as session:
        # Check recipe exists
        from app.db.models import Recipe
        recipe_result = await session.execute(
            select(Recipe.id).where(Recipe.id == recipe_id)
        )
        if recipe_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Recipe not found")

        # Check limit
        count_result = await session.execute(
            select(func.count()).select_from(SavedRecipe).where(SavedRecipe.user_id == user_uuid)
        )
        if count_result.scalar_one() >= MAX_SAVED_RECIPES:
            raise HTTPException(status_code=400, detail=f"Maximum of {MAX_SAVED_RECIPES} saved recipes reached")

        # Check if already saved
        existing = await session.execute(
            select(SavedRecipe).where(
                SavedRecipe.user_id == user_uuid,
                SavedRecipe.recipe_id == recipe_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return {"status": "already_saved"}

        # Ensure profile exists
        profile_result = await session.execute(
            select(UserProfile).where(UserProfile.id == user_uuid)
        )
        if profile_result.scalar_one_or_none() is None:
            session.add(UserProfile(id=user_uuid))
            await session.flush()

        saved = SavedRecipe(user_id=user_uuid, recipe_id=recipe_id)
        session.add(saved)

    return {"status": "saved"}


@router.delete("/{recipe_id}/save", status_code=204)
@limiter.limit("10/minute")
async def unsave_recipe(
    request: Request,
    recipe_id: UUID,
    user: UserContext = Depends(require_user),
) -> None:
    """Remove a recipe from the user's saved list."""
    async with async_transaction() as session:
        result = await session.execute(
            select(SavedRecipe).where(
                SavedRecipe.user_id == uuid_mod.UUID(user.id),
                SavedRecipe.recipe_id == recipe_id,
            )
        )
        saved = result.scalar_one_or_none()
        if saved is None:
            raise HTTPException(status_code=404, detail="Saved recipe not found")
        await session.delete(saved)


@router.get("/{recipe_id}/saved", response_model=dict)
async def check_recipe_saved(
    recipe_id: UUID,
    user: Optional[UserContext] = Depends(optional_user),
) -> dict:
    """Check if a recipe is saved by the current user."""
    if user is None:
        return {"saved": False}

    async with get_async_session() as session:
        result = await session.execute(
            select(SavedRecipe.id).where(
                SavedRecipe.user_id == uuid_mod.UUID(user.id),
                SavedRecipe.recipe_id == recipe_id,
            )
        )
        return {"saved": result.scalar_one_or_none() is not None}
