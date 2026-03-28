"""Backfill product embeddings for existing products.

Usage:
    cd api && python -m scripts.backfill_embeddings
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure api/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.models import Product
from app.db.session import async_transaction
from app.services.embeddings import embed_product_text, embed_texts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

QUERY_BATCH = 1000
ENCODE_BATCH = 256


async def backfill() -> None:
    settings = get_settings()
    if not settings.embedding_enabled:
        logger.error("EMBEDDING_ENABLED is not set to true. Aborting.")
        return

    total_updated = 0
    while True:
        async with async_transaction() as session:
            # Fetch products missing embeddings
            result = await session.execute(
                select(Product.id, Product.department, Product.subcategory, Product.brand, Product.name)
                .where(Product.embedding.is_(None))
                .limit(QUERY_BATCH)
            )
            rows = result.all()

        if not rows:
            break

        logger.info("Processing batch of %d products", len(rows))

        # Build texts and encode in sub-batches
        texts = [
            embed_product_text(
                department=row.department,
                subcategory=row.subcategory,
                brand=row.brand,
                name=row.name,
            )
            for row in rows
        ]

        all_embeddings = []
        for i in range(0, len(texts), ENCODE_BATCH):
            chunk = texts[i : i + ENCODE_BATCH]
            embeddings = embed_texts(chunk)
            if embeddings is None:
                logger.error("embed_texts returned None — is the model loaded?")
                return
            all_embeddings.extend(embeddings)

        # Bulk update
        async with async_transaction() as session:
            for row, emb in zip(rows, all_embeddings):
                await session.execute(
                    update(Product).where(Product.id == row.id).values(embedding=emb)
                )

        total_updated += len(rows)
        logger.info("Updated %d products so far", total_updated)

    logger.info("Backfill complete. Total products updated: %d", total_updated)


if __name__ == "__main__":
    asyncio.run(backfill())
