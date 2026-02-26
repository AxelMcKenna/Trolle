from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional


@dataclass(frozen=True)
class PricingMetrics:
    unit_price: Optional[float]
    unit_measure: Optional[str]


def compute_pricing_metrics(
    *,
    unit_price: Optional[float] = None,
    unit_measure: Optional[str] = None,
) -> PricingMetrics:
    rounded_unit_price = None
    if unit_price:
        rounded_unit_price = float(
            Decimal(str(unit_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )

    return PricingMetrics(
        unit_price=rounded_unit_price,
        unit_measure=unit_measure,
    )


__all__ = ["compute_pricing_metrics", "PricingMetrics"]
