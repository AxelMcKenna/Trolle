"""Tests for pricing service."""
from app.services.pricing import compute_pricing_metrics


def test_compute_pricing_metrics_with_values():
    metrics = compute_pricing_metrics(unit_price=2.75, unit_measure="1L")
    assert metrics.unit_price == 2.75
    assert metrics.unit_measure == "1L"


def test_compute_pricing_metrics_none_values():
    metrics = compute_pricing_metrics(unit_price=None, unit_measure=None)
    assert metrics.unit_price is None
    assert metrics.unit_measure is None


def test_compute_pricing_metrics_rounds_unit_price():
    metrics = compute_pricing_metrics(unit_price=3.333333, unit_measure="100g")
    assert metrics.unit_price == 3.33
