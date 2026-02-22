"""Backfill category and subcategory for existing products.

Usage:
    python -m scripts.backfill_categories

Loads all products where ``category IS NULL``, runs the rule-based
classifier, and batch-updates them in chunks.
"""
import asyncio
import sys
from pathlib import Path

# Ensure the api/ directory is on sys.path so app.* imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

from app.db.models import Product
from app.db.session import async_transaction
from app.services.category_mapper import classify_product

BATCH_SIZE = 1000


async def backfill():
    # Load all products needing backfill in a read transaction
    async with async_transaction() as session:
        result = await session.execute(
            select(Product.id, Product.name, Product.department).where(
                Product.category.is_(None)
            )
        )
        rows = result.all()

    total = len(rows)
    print(f"Found {total} products with category=NULL")

    if total == 0:
        print("Nothing to backfill.")
        return

    classified = 0
    skipped = 0

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        updates = []
        for product_id, name, department in batch:
            category, subcategory = classify_product(department, name)
            if category:
                updates.append({
                    "id": product_id,
                    "category": category,
                    "subcategory": subcategory,
                })
                classified += 1
            else:
                skipped += 1

        if updates:
            async with async_transaction() as session:
                for upd in updates:
                    await session.execute(
                        update(Product)
                        .where(Product.id == upd["id"])
                        .values(category=upd["category"], subcategory=upd["subcategory"])
                    )

        done = min(i + BATCH_SIZE, total)
        print(f"  Processed {done}/{total} — classified: {classified}, skipped: {skipped}")

    print(f"\nDone. Classified {classified}/{total} products ({skipped} could not be mapped).")


if __name__ == "__main__":
    asyncio.run(backfill())
