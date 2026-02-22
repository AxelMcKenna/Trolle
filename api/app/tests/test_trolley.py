"""Tests for trolley feature: schemas, matching, and API endpoint."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.trolley import TrolleyCompareRequest, TrolleyItem
from app.services.matching import normalize_size


class TestNormalizeSize:
    """Tests for size normalization."""

    def test_litres(self):
        assert normalize_size("2 Litres") == "2l"

    def test_litre_singular(self):
        assert normalize_size("1 Litre") == "1l"

    def test_millilitres(self):
        assert normalize_size("500 Millilitres") == "500ml"

    def test_grams(self):
        assert normalize_size("250 Grams") == "250g"

    def test_kilograms(self):
        assert normalize_size("1.5 Kilograms") == "1.5kg"

    def test_already_short(self):
        assert normalize_size("2l") == "2l"

    def test_already_short_g(self):
        assert normalize_size("500g") == "500g"

    def test_none(self):
        assert normalize_size(None) == ""

    def test_empty(self):
        assert normalize_size("") == ""

    def test_pack(self):
        assert normalize_size("6 Pack") == "6pk"

    def test_each(self):
        assert normalize_size("1 Each") == "1ea"

    def test_no_match(self):
        assert normalize_size("Large") == "large"


class TestTrolleySchemas:
    """Tests for trolley request/response schemas."""

    def test_valid_request(self):
        req = TrolleyCompareRequest(
            items=[TrolleyItem(product_id=uuid.uuid4(), quantity=2)],
            lat=-36.8485,
            lon=174.7633,
            radius_km=5,
        )
        assert len(req.items) == 1
        assert req.items[0].quantity == 2

    def test_empty_items_rejected(self):
        with pytest.raises(ValidationError):
            TrolleyCompareRequest(
                items=[],
                lat=-36.8485,
                lon=174.7633,
                radius_km=5,
            )

    def test_too_many_items_rejected(self):
        with pytest.raises(ValidationError):
            TrolleyCompareRequest(
                items=[TrolleyItem(product_id=uuid.uuid4(), quantity=1) for _ in range(51)],
                lat=-36.8485,
                lon=174.7633,
                radius_km=5,
            )

    def test_quantity_bounds(self):
        with pytest.raises(ValidationError):
            TrolleyItem(product_id=uuid.uuid4(), quantity=0)
        with pytest.raises(ValidationError):
            TrolleyItem(product_id=uuid.uuid4(), quantity=100)

    def test_lat_out_of_range(self):
        with pytest.raises(ValidationError):
            TrolleyCompareRequest(
                items=[TrolleyItem(product_id=uuid.uuid4(), quantity=1)],
                lat=-30.0,
                lon=174.7633,
                radius_km=5,
            )

    def test_lon_out_of_range(self):
        with pytest.raises(ValidationError):
            TrolleyCompareRequest(
                items=[TrolleyItem(product_id=uuid.uuid4(), quantity=1)],
                lat=-36.8485,
                lon=150.0,
                radius_km=5,
            )

    def test_radius_too_large(self):
        with pytest.raises(ValidationError):
            TrolleyCompareRequest(
                items=[TrolleyItem(product_id=uuid.uuid4(), quantity=1)],
                lat=-36.8485,
                lon=174.7633,
                radius_km=11,
            )

    def test_default_quantity(self):
        item = TrolleyItem(product_id=uuid.uuid4())
        assert item.quantity == 1

    def test_max_items_accepted(self):
        req = TrolleyCompareRequest(
            items=[TrolleyItem(product_id=uuid.uuid4(), quantity=1) for _ in range(50)],
            lat=-36.8485,
            lon=174.7633,
            radius_km=5,
        )
        assert len(req.items) == 50


class TestTrolleyEndpoint:
    """Tests for POST /trolley/compare endpoint."""

    def test_trolley_compare_invalid_body(self, client):
        """Empty body should return 422."""
        response = client.post("/trolley/compare", json={})
        assert response.status_code == 422

    def test_trolley_compare_missing_items(self, client):
        """Missing items should return 422."""
        response = client.post("/trolley/compare", json={
            "lat": -36.8485,
            "lon": 174.7633,
            "radius_km": 5,
        })
        assert response.status_code == 422

    def test_trolley_compare_empty_items(self, client):
        """Empty items list should return 422."""
        response = client.post("/trolley/compare", json={
            "items": [],
            "lat": -36.8485,
            "lon": 174.7633,
            "radius_km": 5,
        })
        assert response.status_code == 422

    def test_trolley_compare_invalid_location(self, client):
        """Location outside NZ should return 422."""
        response = client.post("/trolley/compare", json={
            "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
            "lat": -20.0,
            "lon": 174.7633,
            "radius_km": 5,
        })
        assert response.status_code == 422

    def test_trolley_compare_success(self, client):
        """Valid request should return comparison data."""
        mock_result = {
            "stores": [],
            "items": [],
            "summary": {"total_items": 1, "total_stores": 0, "complete_stores": 0},
        }

        with patch("app.routes.trolley.compare_trolley", AsyncMock(return_value=mock_result)):
            response = client.post("/trolley/compare", json={
                "items": [{"product_id": str(uuid.uuid4()), "quantity": 2}],
                "lat": -36.8485,
                "lon": 174.7633,
                "radius_km": 5,
            })

        assert response.status_code == 200
        data = response.json()
        assert "stores" in data
        assert "items" in data
        assert "summary" in data
        assert data["summary"]["total_items"] == 1
