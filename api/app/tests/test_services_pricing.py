"""Tests for pricing service."""
from __future__ import annotations

import pytest

from app.services.pricing import PricingMetrics, compute_pricing_metrics


class TestComputePricingMetrics:
    """Tests for compute_pricing_metrics function."""

    def test_unit_price_passthrough(self):
        """Should pass through unit_price value."""
        metrics = compute_pricing_metrics(unit_price=2.75, unit_measure="1L")
        assert metrics.unit_price == 2.75

    def test_unit_measure_passthrough(self):
        """Should pass through unit_measure value."""
        metrics = compute_pricing_metrics(unit_price=5.00, unit_measure="1kg")
        assert metrics.unit_measure == "1kg"

    def test_none_unit_price(self):
        """Should return None unit_price when not provided."""
        metrics = compute_pricing_metrics(unit_price=None, unit_measure="100g")
        assert metrics.unit_price is None

    def test_none_unit_measure(self):
        """Should return None unit_measure when not provided."""
        metrics = compute_pricing_metrics(unit_price=3.50, unit_measure=None)
        assert metrics.unit_measure is None

    def test_both_none(self):
        """Should handle both values being None."""
        metrics = compute_pricing_metrics(unit_price=None, unit_measure=None)
        assert metrics.unit_price is None
        assert metrics.unit_measure is None

    def test_unit_price_rounded_to_2_decimal(self):
        """Unit price should be rounded to 2 decimal places."""
        metrics = compute_pricing_metrics(unit_price=3.33333, unit_measure="100g")
        assert metrics.unit_price == 3.33

    def test_unit_price_rounded_up(self):
        """Unit price rounding should follow standard rules."""
        metrics = compute_pricing_metrics(unit_price=3.335, unit_measure="100g")
        assert metrics.unit_price == 3.34

    def test_various_unit_measures(self):
        """Should accept various unit measure formats."""
        for measure in ["1kg", "100g", "1L", "100ml", "1ea"]:
            metrics = compute_pricing_metrics(unit_price=5.00, unit_measure=measure)
            assert metrics.unit_measure == measure

    def test_zero_unit_price(self):
        """Should handle zero unit price (falsy but valid)."""
        metrics = compute_pricing_metrics(unit_price=0.0, unit_measure="1kg")
        assert metrics.unit_price is None

    def test_small_unit_price(self):
        """Should handle very small unit prices."""
        metrics = compute_pricing_metrics(unit_price=0.01, unit_measure="1ea")
        assert metrics.unit_price == 0.01


class TestPricingMetricsDataclass:
    """Tests for PricingMetrics dataclass."""

    def test_pricing_metrics_immutable(self):
        """PricingMetrics should be immutable (frozen)."""
        metrics = PricingMetrics(unit_price=2.75, unit_measure="1L")
        with pytest.raises(AttributeError):
            metrics.unit_price = 10.0

    def test_pricing_metrics_allows_none(self):
        """PricingMetrics should allow None values."""
        metrics = PricingMetrics(unit_price=None, unit_measure=None)
        assert metrics.unit_price is None
        assert metrics.unit_measure is None

    def test_pricing_metrics_equality(self):
        """PricingMetrics with same values should be equal."""
        m1 = PricingMetrics(unit_price=2.75, unit_measure="1L")
        m2 = PricingMetrics(unit_price=2.75, unit_measure="1L")
        assert m1 == m2
