from __future__ import annotations

from dataclasses import dataclass
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
    return PricingMetrics(
        unit_price=round(unit_price, 2) if unit_price else None,
        unit_measure=unit_measure,
    )


__all__ = ["compute_pricing_metrics", "PricingMetrics"]
