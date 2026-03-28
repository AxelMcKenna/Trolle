#!/usr/bin/env python3
"""Seed the database with common NZ recipes.

Usage:
    cd api && python scripts/seed_recipes.py

Idempotent: only inserts recipes where is_seeded=True and no existing
seeded recipe has the same title.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from api/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Recipe, RecipeIngredient
from app.db.session import transaction
from app.services.recipe import parse_ingredient


SEED_RECIPES = [
    {
        "title": "Spaghetti Bolognese",
        "description": "Classic Kiwi spag bol — a weeknight staple.",
        "servings": 4,
        "image_url": "https://images.unsplash.com/photo-1622973536968-3ead9e780960?w=600&h=400&fit=crop",
        "ingredients": [
            "500g beef mince",
            "1 onion",
            "2 cloves garlic",
            "400g canned tomatoes",
            "2 tbsp tomato paste",
            "500g spaghetti",
            "1 carrot",
            "1 stalk celery",
            "1 tbsp olive oil",
            "salt and pepper",
        ],
    },
    {
        "title": "Chicken Stir-Fry",
        "description": "Quick and healthy chicken and vegetable stir-fry.",
        "servings": 4,
        "image_url": "https://images.unsplash.com/photo-1728910107534-e04e261768ae?w=600&h=400&fit=crop",
        "ingredients": [
            "500g chicken breast",
            "1 capsicum",
            "1 broccoli",
            "2 carrots",
            "2 tbsp soy sauce",
            "1 tbsp sesame oil",
            "2 cloves garlic",
            "1 tbsp cornflour",
            "250g rice",
        ],
    },
    {
        "title": "Shepherd's Pie",
        "description": "Hearty lamb mince pie with mashed potato topping.",
        "servings": 6,
        "image_url": "https://images.unsplash.com/photo-1627662057429-58a292b60606?w=600&h=400&fit=crop",
        "ingredients": [
            "500g lamb mince",
            "1 onion",
            "2 carrots",
            "1 cup frozen peas",
            "2 tbsp tomato paste",
            "1 cup beef stock",
            "1kg potatoes",
            "50g butter",
            "100ml milk",
        ],
    },
    {
        "title": "Fish & Chips",
        "description": "Beer-battered fish with crispy chips — a Kiwi classic.",
        "servings": 4,
        "image_url": "https://images.unsplash.com/photo-1722105344016-0df8537c1799?w=600&h=400&fit=crop",
        "ingredients": [
            "4 pieces fish fillets",
            "1 cup flour",
            "1 cup beer",
            "1kg potatoes",
            "1l vegetable oil",
            "1 lemon",
            "salt and pepper",
        ],
    },
    {
        "title": "Butter Chicken",
        "description": "Creamy, mild curry that the whole family loves.",
        "servings": 4,
        "image_url": "https://images.unsplash.com/photo-1742599361539-f096753d1100?w=600&h=400&fit=crop",
        "ingredients": [
            "500g chicken thigh",
            "400g canned tomatoes",
            "200ml cream",
            "2 tbsp butter",
            "1 onion",
            "3 cloves garlic",
            "2 tbsp curry paste",
            "1 tbsp garam masala",
            "300g rice",
        ],
    },
    {
        "title": "Banana Cake",
        "description": "Moist banana cake — perfect for using up ripe bananas.",
        "servings": 8,
        "image_url": "https://images.unsplash.com/photo-1550597621-b7aa1060b623?w=600&h=400&fit=crop",
        "ingredients": [
            "3 bananas",
            "2 cups flour",
            "1 cup sugar",
            "100g butter",
            "2 eggs",
            "1 tsp baking soda",
            "1 tsp vanilla extract",
            "100ml milk",
        ],
    },
    {
        "title": "Beef Nachos",
        "description": "Loaded nachos with seasoned mince, cheese, and salsa.",
        "servings": 4,
        "image_url": "https://images.unsplash.com/photo-1582169296194-e4d644c48063?w=600&h=400&fit=crop",
        "ingredients": [
            "500g beef mince",
            "1 packet taco seasoning",
            "200g corn chips",
            "1 cup grated cheese",
            "1 avocado",
            "200g sour cream",
            "200g salsa",
            "1 tomato",
            "1 onion",
        ],
    },
    {
        "title": "Pumpkin Soup",
        "description": "Creamy roasted pumpkin soup — comfort in a bowl.",
        "servings": 6,
        "image_url": "https://images.unsplash.com/photo-1604152135912-04a022e23696?w=600&h=400&fit=crop",
        "ingredients": [
            "1kg pumpkin",
            "1 onion",
            "2 cloves garlic",
            "500ml chicken stock",
            "200ml cream",
            "1 tbsp olive oil",
            "salt and pepper",
        ],
    },
    {
        "title": "Lamb Roast",
        "description": "Sunday roast lamb with roasted vegetables.",
        "servings": 6,
        "image_url": "https://images.unsplash.com/photo-1734987052573-0fbe611842ae?w=600&h=400&fit=crop",
        "ingredients": [
            "1.5kg lamb leg",
            "1kg potatoes",
            "500g kumara",
            "4 carrots",
            "1 onion",
            "4 cloves garlic",
            "2 sprigs rosemary",
            "2 tbsp olive oil",
        ],
    },
    {
        "title": "Chicken Caesar Salad",
        "description": "Classic Caesar salad with grilled chicken.",
        "servings": 4,
        "image_url": "https://images.unsplash.com/photo-1556386734-4227a180d19e?w=600&h=400&fit=crop",
        "ingredients": [
            "500g chicken breast",
            "1 cos lettuce",
            "100g parmesan cheese",
            "1 cup croutons",
            "4 rashers bacon",
            "100ml caesar dressing",
            "1 lemon",
        ],
    },
]


def main() -> None:
    with transaction() as session:
        # Get existing seeded recipes
        existing_recipes = {
            r.title: r
            for r in session.query(Recipe).filter(Recipe.is_seeded == True).all()
        }

        added = 0
        updated = 0

        # Update image URLs on existing seeded recipes that are missing them
        for recipe_data in SEED_RECIPES:
            if recipe_data["title"] in existing_recipes:
                recipe = existing_recipes[recipe_data["title"]]
                new_url = recipe_data.get("image_url")
                if new_url and not recipe.image_url:
                    recipe.image_url = new_url
                    updated += 1

        for recipe_data in SEED_RECIPES:
            if recipe_data["title"] in existing_recipes:
                continue

            recipe = Recipe(
                title=recipe_data["title"],
                description=recipe_data["description"],
                servings=recipe_data["servings"],
                image_url=recipe_data.get("image_url"),
                is_public=True,
                is_seeded=True,
                created_by=None,
            )
            session.add(recipe)
            session.flush()

            for ing_text in recipe_data["ingredients"]:
                parsed = parse_ingredient(ing_text)
                ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    description=ing_text,
                    quantity=parsed["quantity"],
                    unit=parsed["unit"],
                    display_name=parsed["display_name"],
                    optional=False,
                )
                session.add(ingredient)

            added += 1

        print(f"Seeded {added} new recipes, updated {updated} images ({len(existing_recipes)} already existed)")


if __name__ == "__main__":
    main()
