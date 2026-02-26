"""Batch geocode stores using Nominatim (OpenStreetMap).

Usage:
    python -m scripts.geocode_stores
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import text

from app.db.session import get_async_session

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Suppress SQLAlchemy engine logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "Troll-E/1.0 (grocery price comparison; contact@troll-e.co.nz)"}

CHAIN_SEARCH = {
    "countdown": "Woolworths",
    "new_world": "New World",
    "paknsave": "PAK'nSAVE",
}


async def geocode_store(client: httpx.AsyncClient, name: str, address: str | None, chain: str) -> tuple[float, float] | None:
    """Geocode a single store. Returns (lat, lon) or None."""
    chain_label = CHAIN_SEARCH.get(chain, chain)
    suburb = name.replace(chain_label, "").replace("Woolworths", "").strip()

    # Build queries in priority order
    queries = []

    # For PAK'nSAVE with proper addresses, use address first
    if address and "," in address:
        queries.append(address + ", New Zealand")

    # Store name + NZ
    queries.append(f"{name}, New Zealand")

    # Just the suburb + chain type as amenity search
    if suburb:
        queries.append(f"{suburb}, New Zealand")

    for query in queries:
        try:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "nz"},
                headers=HEADERS,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                if -47.5 <= lat <= -34.0 and 165.0 <= lon <= 179.0:
                    return lat, lon
        except Exception as e:
            logger.warning("Geocode query %r failed: %s", query, e)

        # Respect Nominatim rate limit
        await asyncio.sleep(1.05)

    return None


async def main():
    async with get_async_session() as session:
        result = await session.execute(
            text("SELECT id, name, address, chain FROM stores WHERE lat IS NULL ORDER BY chain, name")
        )
        stores = result.fetchall()

    logger.info("Found %d stores without coordinates", len(stores))

    geocoded = 0
    failed = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for i, (store_id, name, address, chain) in enumerate(stores, 1):
            coords = await geocode_store(client, name, address, chain)

            if coords:
                lat, lon = coords
                async with get_async_session() as session:
                    await session.execute(
                        text("UPDATE stores SET lat = :lat, lon = :lon WHERE id = :id"),
                        {"lat": lat, "lon": lon, "id": store_id},
                    )
                    await session.commit()
                geocoded += 1
                if i % 20 == 0 or i <= 5:
                    logger.info("[%d/%d] %s -> (%.4f, %.4f) | %d geocoded so far", i, len(stores), name, lat, lon, geocoded)
            else:
                failed.append(name)
                if i <= 10:
                    logger.warning("[%d/%d] %s -> FAILED", i, len(stores), name)

    logger.info("Done! Geocoded %d/%d stores. %d failed.", geocoded, len(stores), len(failed))
    if failed:
        logger.info("Failed stores (%d): %s", len(failed), ", ".join(failed[:30]))


if __name__ == "__main__":
    asyncio.run(main())
