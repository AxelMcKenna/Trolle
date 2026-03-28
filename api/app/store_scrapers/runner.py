"""CLI runner for store location scrapers.

Usage:
    # Run all chains
    python -m app.store_scrapers.runner

    # Run specific chains (comma-separated)
    python -m app.store_scrapers.runner countdown

    # Or via env var
    TROLLE_STORE_CHAINS=countdown python -m app.store_scrapers.runner
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict

from sqlalchemy import text

from app.db.session import get_async_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# All chains use static JSON store lists
_JSON_STORE_CHAINS: Dict[str, str] = {
    "countdown": "countdown_stores.json",
    "paknsave": "paknsave_stores.json",
    "new_world": "newworld_stores.json",
    "mad_butcher": "mad_butcher_stores.json",
    "prestons": "prestons_stores.json",
}

CHAIN_DISPLAY_NAMES: Dict[str, str] = {
    "countdown": "Woolworths",
    "new_world": "New World",
    "paknsave": "PAK'nSAVE",
    "mad_butcher": "Mad Butcher",
    "prestons": "Preston's",
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


def _pick_bool(store: dict, *keys: str) -> bool | None:
    """Return first boolean-like value from provided keys."""
    for key in keys:
        value = store.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ("true", "yes", "1"):
                return True
            if value.lower() in ("false", "no", "0"):
                return False
    return None


# Chain-level fulfillment defaults applied when store JSON lacks specific values
CHAIN_FULFILLMENT_DEFAULTS: dict[str, dict] = {
    "countdown": {
        "delivery_fee_nzd": 14.00,
        "free_delivery_threshold_nzd": 150.00,
        "cc_fee_nzd": 0.0,
        "min_order_nzd": 0.0,
    },
    "paknsave": {
        "delivery_fee_nzd": 0.0,
        "free_delivery_threshold_nzd": 0.0,
        "cc_fee_nzd": 0.0,
        "min_order_nzd": 0.0,
    },
    "new_world": {
        "delivery_fee_nzd": 9.00,
        "free_delivery_threshold_nzd": 120.00,
        "cc_fee_nzd": 0.0,
        "min_order_nzd": 0.0,
    },
}


async def upsert_stores(chain: str, stores: list[dict]) -> tuple[int, int]:
    """Upsert stores into DB. Returns (upserted, skipped)."""
    upserted = 0
    skipped = 0
    defaults = CHAIN_FULFILLMENT_DEFAULTS.get(chain, {})

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

            # Fulfillment fields: read from store JSON, fall back to chain defaults
            click_collect = _pick_bool(store, "clickAndCollect", "click_collect")
            delivery_flag = _pick_bool(store, "delivery")
            delivery_fee = _pick_float(store, "delivery_fee_nzd") or defaults.get("delivery_fee_nzd")
            min_order = _pick_float(store, "min_order_nzd") or defaults.get("min_order_nzd")
            cc_fee = _pick_float(store, "cc_fee_nzd") or defaults.get("cc_fee_nzd")
            free_threshold = _pick_float(store, "free_delivery_threshold_nzd") or defaults.get("free_delivery_threshold_nzd")

            await session.execute(
                text("""
                    INSERT INTO stores (id, chain, name, address, region, lat, lon, url, api_id,
                                        click_collect, delivery, delivery_fee_nzd, min_order_nzd,
                                        cc_fee_nzd, free_delivery_threshold_nzd, fulfillment_updated_at)
                    VALUES (gen_random_uuid(), :chain, :name, :address, :region, :lat, :lon, :url, :api_id,
                            :click_collect, :delivery, :delivery_fee_nzd, :min_order_nzd,
                            :cc_fee_nzd, :free_delivery_threshold_nzd, now())
                    ON CONFLICT (chain, name) DO UPDATE SET
                        address                     = COALESCE(EXCLUDED.address, stores.address),
                        region                      = COALESCE(EXCLUDED.region, stores.region),
                        lat                         = COALESCE(EXCLUDED.lat, stores.lat),
                        lon                         = COALESCE(EXCLUDED.lon, stores.lon),
                        url                         = COALESCE(EXCLUDED.url, stores.url),
                        api_id                      = COALESCE(EXCLUDED.api_id, stores.api_id),
                        click_collect               = COALESCE(EXCLUDED.click_collect, stores.click_collect),
                        delivery                    = COALESCE(EXCLUDED.delivery, stores.delivery),
                        delivery_fee_nzd            = COALESCE(EXCLUDED.delivery_fee_nzd, stores.delivery_fee_nzd),
                        min_order_nzd               = COALESCE(EXCLUDED.min_order_nzd, stores.min_order_nzd),
                        cc_fee_nzd                  = COALESCE(EXCLUDED.cc_fee_nzd, stores.cc_fee_nzd),
                        free_delivery_threshold_nzd = COALESCE(EXCLUDED.free_delivery_threshold_nzd, stores.free_delivery_threshold_nzd),
                        fulfillment_updated_at      = now()
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
                    "click_collect": click_collect,
                    "delivery": delivery_flag,
                    "delivery_fee_nzd": delivery_fee,
                    "min_order_nzd": min_order,
                    "cc_fee_nzd": cc_fee,
                    "free_delivery_threshold_nzd": free_threshold,
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
    """Load stores from JSON and upsert into DB."""
    json_file = _JSON_STORE_CHAINS.get(chain)
    if not json_file:
        logger.error(f"Unknown chain: {chain}. Available: {', '.join(_JSON_STORE_CHAINS.keys())}")
        return
    await run_json_chain(chain, json_file)


async def main(chains: list[str] | None = None) -> None:
    """Run store scrapers for given chains (or all)."""
    if not chains:
        chains = list(_JSON_STORE_CHAINS.keys())

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
        raw = os.environ.get("TROLLE_STORE_CHAINS")

    target_chains = [c.strip() for c in raw.split(",") if c.strip()] if raw else None
    asyncio.run(main(target_chains))
