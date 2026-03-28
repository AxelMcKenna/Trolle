"""Fulfillment fee computation and chain-level defaults.

Provides ``compute_fulfillment_fee`` which calculates the delivery or
click-and-collect fee for a given store and grocery subtotal, falling
back to chain-level defaults when store-specific values are NULL.
"""
from __future__ import annotations

from typing import Optional


# Chain-level defaults for fulfillment fees (NZD).  Store-level columns
# override these when populated.
CHAIN_FULFILLMENT_DEFAULTS: dict[str, dict[str, float]] = {
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


def _resolve(store_value: Optional[float], chain: str, key: str) -> float:
    """Return the store-level value if set, otherwise the chain default, else 0."""
    if store_value is not None:
        return store_value
    return CHAIN_FULFILLMENT_DEFAULTS.get(chain, {}).get(key, 0.0)


def compute_fulfillment_fee(
    *,
    chain: str,
    subtotal: float,
    method: str,
    delivery_fee_nzd: Optional[float] = None,
    free_delivery_threshold_nzd: Optional[float] = None,
    cc_fee_nzd: Optional[float] = None,
) -> float:
    """Calculate the fulfillment fee for a store given the grocery subtotal.

    Args:
        chain: Store chain identifier.
        subtotal: Total grocery cost before fees.
        method: One of ``"in_store"``, ``"click_collect"``, ``"delivery"``.
        delivery_fee_nzd: Store-level delivery fee (or None for chain default).
        free_delivery_threshold_nzd: Subtotal above which delivery is free.
        cc_fee_nzd: Store-level click-and-collect fee (or None for chain default).

    Returns:
        The fee in NZD (0.0 for in-store).
    """
    if method == "in_store":
        return 0.0

    if method == "click_collect":
        return _resolve(cc_fee_nzd, chain, "cc_fee_nzd")

    if method == "delivery":
        threshold = _resolve(free_delivery_threshold_nzd, chain, "free_delivery_threshold_nzd")
        if threshold > 0 and subtotal >= threshold:
            return 0.0
        return _resolve(delivery_fee_nzd, chain, "delivery_fee_nzd")

    # "any" or unknown — return 0 (caller picks cheapest option)
    return 0.0


def store_supports_method(
    *,
    method: str,
    click_collect: Optional[bool],
    delivery: Optional[bool],
) -> bool:
    """Check whether a store supports a given fulfillment method.

    NULL capability flags are treated as *unknown* and included (not filtered
    out) so we avoid hiding stores before data is fully populated.
    """
    if method == "in_store" or method == "any":
        return True
    if method == "click_collect":
        return click_collect is not False  # True or None (unknown) passes
    if method == "delivery":
        return delivery is not False  # True or None (unknown) passes
    return True


__all__ = [
    "CHAIN_FULFILLMENT_DEFAULTS",
    "compute_fulfillment_fee",
    "store_supports_method",
]
