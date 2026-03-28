from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# --- Create / Input ---

class RecipeIngredientCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Optional[float] = None
    unit: Optional[str] = None
    display_name: Optional[str] = None
    optional: bool = False


class RecipeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1024)
    servings: int = Field(4, ge=1, le=100)
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    ingredients: list[RecipeIngredientCreate] = Field(..., min_length=1, max_length=50)


# --- Response ---

class RecipeIngredientResponse(BaseModel):
    id: str
    description: str
    quantity: Optional[float]
    unit: Optional[str]
    display_name: str
    optional: bool


class RecipeResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    servings: int
    image_url: Optional[str]
    source_url: Optional[str]
    is_public: bool
    is_seeded: bool
    created_by: Optional[str]
    ingredients: list[RecipeIngredientResponse]


class RecipeListItem(BaseModel):
    id: str
    title: str
    description: Optional[str]
    servings: int
    image_url: Optional[str]
    ingredient_count: int


class RecipeListResponse(BaseModel):
    items: list[RecipeListItem]
    total: int


# --- Cost Comparison ---

class RecipeCostRequest(BaseModel):
    recipe_id: UUID
    lat: float
    lon: float
    radius_km: float = Field(ge=1, le=10)

    @validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not (-47 <= v <= -34):
            raise ValueError("Latitude must be within New Zealand bounds (-47 to -34)")
        return v

    @validator("lon")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if not (165 <= v <= 179):
            raise ValueError("Longitude must be within New Zealand bounds (165 to 179)")
        return v


class RecipeIngredientMatch(BaseModel):
    ingredient_id: str
    ingredient_description: str
    display_name: str
    optional: bool
    available: bool
    matched_product_id: Optional[str]
    matched_product_name: Optional[str]
    matched_product_image: Optional[str]
    price: Optional[float]
    quantity: Optional[float]
    unit: Optional[str]


class RecipeStoreBreakdown(BaseModel):
    store_id: str
    store_name: str
    chain: str
    distance_km: float
    estimated_total: float
    items_available: int
    items_total: int
    is_complete: bool
    ingredients: list[RecipeIngredientMatch]


class RecipeCostResponse(BaseModel):
    recipe: RecipeListItem
    stores: list[RecipeStoreBreakdown]
    summary: dict


__all__ = [
    "RecipeIngredientCreate",
    "RecipeCreate",
    "RecipeIngredientResponse",
    "RecipeResponse",
    "RecipeListItem",
    "RecipeListResponse",
    "RecipeCostRequest",
    "RecipeIngredientMatch",
    "RecipeStoreBreakdown",
    "RecipeCostResponse",
]
