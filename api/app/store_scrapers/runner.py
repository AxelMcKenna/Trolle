"""CLI runner for store location scrapers.

Usage:
    # Run all chains
    python -m app.store_scrapers.runner

    # Run specific chains (comma-separated)
    python -m app.store_scrapers.runner countdown

    # Or via env var
    GROCIFY_STORE_CHAINS=countdown python -m app.store_scrapers.runner
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Type

from sqlalchemy import text

from app.db.session import get_async_session
from app.store_scrapers.base import StoreLocationScraper
from app.store_scrapers.countdown import CountdownLocationScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

STORE_CHAINS: Dict[str, Type[StoreLocationScraper]] = {
    "countdown": CountdownLocationScraper,
}

# Foodstuffs chains use static JSON store lists (no scraper needed)
_JSON_STORE_CHAINS: Dict[str, str] = {
    "paknsave": "paknsave_stores.json",
    "new_world": "newworld_stores.json",
}

CHAIN_DISPLAY_NAMES: Dict[str, str] = {
    "countdown": "Woolworths",
    "new_world": "New World",
    "paknsave": "PAK'nSAVE",
}


def _pick_str(store: dict, *keys: str) -> str | None:
    """Return first non-empty string-like value from provided keys."""
    for key in keys:
        value = store.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
            continue
        text_val = str(value).strip()
        if text_val:
            return text_val
    return None


def _pick_float(store: dict, *keys: str) -> float | None:
    """Return first value parseable as float from provided keys."""
    for key in keys:
        value = store.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


async def upsert_stores(chain: str, stores: list[dict]) -> tuple[int, int]:
    """Upsert stores into DB. Returns (upserted, skipped)."""
    upserted = 0
    skipped = 0

    async with get_async_session() as session:
        for store in stores:
            name = _pick_str(store, "name", "Name", "label", "title", "storeName", "store_name")
            if not name:
                skipped += 1
                continue

            # Normalize ALL-CAPS names to title case
            if name == name.upper() and not name.isnumeric():
                name = name.title()

            # Prepend chain display name if not already present
            display = CHAIN_DISPLAY_NAMES.get(chain, "")
            if display:
                display_lower = display.lower()
                # Strip display name if it appears as a suffix
                if name.lower().endswith(f" {display_lower}"):
                    name = name[: -(len(display) + 1)].strip()
                if not name.lower().startswith(display_lower):
                    name = f"{display} {name}"

            address = _pick_str(store, "address", "Address", "FullAddress")
            if not address:
                address_parts = [
                    _pick_str(store, "Address", "address"),
                    _pick_str(store, "City", "city"),
                    _pick_str(store, "State", "state", "region"),
                    _pick_str(store, "ZipPostalCode", "postcode"),
                ]
                address = ", ".join([part for part in address_parts if part]) or None

            region = _pick_str(store, "region", "Region", "State", "state", "AreaName", "City", "city")
            lat = _pick_float(store, "lat", "latitude", "Latitude")
            lon = _pick_float(store, "lon", "lng", "longitude", "Longitude")
            url = _pick_str(store, "url", "StoreLocationUrl", "StoreDetailsUrl", "GoogleMapLocation")

            api_id = _pick_str(store, "api_id", "id", "storeId", "store_id")

            await session.execute(
                text("""
                    INSERT INTO stores (id, chain, name, address, region, lat, lon, url, api_id)
                    VALUES (gen_random_uuid(), :chain, :name, :address, :region, :lat, :lon, :url, :api_id)
                    ON CONFLICT (chain, name) DO UPDATE SET
                        address = COALESCE(EXCLUDED.address, stores.address),
                        region  = COALESCE(EXCLUDED.region, stores.region),
                        lat     = COALESCE(EXCLUDED.lat, stores.lat),
                        lon     = COALESCE(EXCLUDED.lon, stores.lon),
                        url     = COALESCE(EXCLUDED.url, stores.url),
                        api_id  = COALESCE(EXCLUDED.api_id, stores.api_id)
                """),
                {
                    "chain": chain,
                    "name": name,
                    "address": address,
                    "region": region,
                    "lat": lat,
                    "lon": lon,
                    "url": url,
                    "api_id": api_id,
                },
            )
            upserted += 1

        await session.commit()

    return upserted, skipped


async def run_json_chain(chain: str, filename: str) -> None:
    """Load stores from a static JSON file and upsert into DB."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    json_path = data_dir / filename

    logger.info(f"[{chain}] Loading stores from {json_path}")
    try:
        with open(json_path) as f:
            stores = json.load(f)

        logger.info(f"[{chain}] Loaded {len(stores)} stores from JSON")

        if stores:
            upserted, skipped = await upsert_stores(chain, stores)
            logger.info(f"[{chain}] Upserted {upserted}, skipped {skipped}")
        else:
            logger.warning(f"[{chain}] No stores in JSON file")

    except FileNotFoundError:
        logger.error(f"[{chain}] JSON file not found: {json_path}")
    except Exception:
        logger.exception(f"[{chain}] Failed to load stores from JSON")


async def run_chain(chain: str) -> None:
    """Run a single store scraper (or JSON load) and upsert results."""
    # Check JSON-based chains first
    json_file = _JSON_STORE_CHAINS.get(chain)
    if json_file:
        await run_json_chain(chain, json_file)
        return

    scraper_cls = STORE_CHAINS.get(chain)
    if not scraper_cls:
        all_chains = list(STORE_CHAINS.keys()) + list(_JSON_STORE_CHAINS.keys())
        logger.error(f"Unknown chain: {chain}. Available: {', '.join(all_chains)}")
        return

    logger.info(f"[{chain}] Starting store scrape...")
    try:
        async with scraper_cls() as scraper:
            stores = await scraper.fetch_stores()

        logger.info(f"[{chain}] Fetched {len(stores)} stores")

        if stores:
            upserted, skipped = await upsert_stores(chain, stores)
            logger.info(f"[{chain}] Upserted {upserted}, skipped {skipped}")
        else:
            logger.warning(f"[{chain}] No stores returned")

    except Exception:
        logger.exception(f"[{chain}] Store scrape failed")


async def main(chains: list[str] | None = None) -> None:
    """Run store scrapers for given chains (or all)."""
    if not chains:
        chains = list(STORE_CHAINS.keys()) + list(_JSON_STORE_CHAINS.keys())

    logger.info(f"Running store scrapers for: {', '.join(chains)}")

    for chain in chains:
        await run_chain(chain)
        await asyncio.sleep(2)  # Be respectful between chains

    logger.info("Store scraping complete.")


if __name__ == "__main__":
    # Accept chains from CLI arg or env var
    raw = None
    if len(sys.argv) > 1:
        raw = sys.argv[1]
    else:
        raw = os.environ.get("GROCIFY_STORE_CHAINS")

    target_chains = [c.strip() for c in raw.split(",") if c.strip()] if raw else None
    asyncio.run(main(target_chains))
