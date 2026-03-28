"""Backfill structured size fields for existing products.

Parses the size/name of each product to populate volume_ml, weight_g,
pack_count, normalized_name, and normalized_brand.

Usage:
    cd api/
    python -m scripts.backfill_structured_sizes [--batch-size 1000] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure the api package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

from app.db.models import Product
from app.db.session import async_transaction
from app.services.normalizer import (
    clean_product_name,
    normalize_brand,
    parse_structured_size,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def backfill(batch_size: int = 1000, dry_run: bool = False) -> None:
    offset = 0
    total_updated = 0

    while True:
        async with async_transaction() as session:
            result = await session.execute(
                select(Product.id, Product.name, Product.brand, Product.size)
                .where(Product.volume_ml.is_(None) & Product.weight_g.is_(None) & Product.normalized_name.is_(None))
                .limit(batch_size)
                .offset(offset)
            )
            rows = result.all()

            if not rows:
                break

            logger.info(f"Processing batch of {len(rows)} products (offset={offset})")

            for product_id, name, brand, size in rows:
                structured = parse_structured_size(size or name or "")
                norm_name = clean_product_name(name or "", brand)
                norm_brand = normalize_brand(brand) if brand else None

                if dry_run:
                    logger.info(
                        f"  [DRY RUN] {name[:60]:60s} | size={size!r:20s} | "
                        f"vol={structured.volume_ml} wt={structured.weight_g} "
                        f"pk={structured.pack_count} type={structured.size_type}"
                    )
                    continue

                await session.execute(
                    update(Product)
                    .where(Product.id == product_id)
                    .values(
                        volume_ml=structured.volume_ml,
                        weight_g=structured.weight_g,
                        pack_count=structured.pack_count,
                        normalized_name=norm_name or None,
                        normalized_brand=norm_brand,
                    )
                )

            if not dry_run:
                total_updated += len(rows)

            # If we got fewer than batch_size, we're done
            if len(rows) < batch_size:
                break

            offset += batch_size

    logger.info(f"Backfill complete: {total_updated} products updated")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill structured product size fields")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true", help="Log changes without writing to DB")
    args = parser.parse_args()

    asyncio.run(backfill(batch_size=args.batch_size, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
