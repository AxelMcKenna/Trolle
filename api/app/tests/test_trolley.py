"""Tests for trolley feature: schemas, matching, and API endpoint."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.trolley import TrolleyCompareRequest, TrolleyItem
from app.services.matching import _clean_search_name, normalize_size
from app.services.trolley import _effective_price


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

    def test_multipack_format(self):
        """Multipack sizes: regex captures the first number+unit pair."""
        assert normalize_size("6 x 330ml") == "330ml"

    def test_decimal_trailing_zero(self):
        """Trailing zeros should be stripped: '1.50 kg' -> '1.5kg'."""
        assert normalize_size("1.50 Kilograms") == "1.5kg"

    def test_integer_no_decimal(self):
        """Whole numbers should not have .0: '2.0 litres' -> '2l'."""
        assert normalize_size("2.0 Litres") == "2l"


class TestCleanSearchName:
    """Tests for _clean_search_name (brand + embedded size removal)."""

    def test_brand_at_start(self):
        assert _clean_search_name("Woolworths Spaghetti Pasta", "Woolworths") == "spaghetti pasta"

    def test_brand_in_middle(self):
        assert _clean_search_name("Fresh Woolworths Milk", "Woolworths") == "fresh milk"

    def test_brand_repeated(self):
        result = _clean_search_name("Woolworths Spaghetti Woolworths Pasta", "Woolworths")
        assert result == "spaghetti pasta"

    def test_brand_case_insensitive(self):
        result = _clean_search_name("COUNTDOWN Free Range Eggs", "Countdown")
        assert result == "free range eggs"

    def test_no_brand(self):
        assert _clean_search_name("Spaghetti Pasta", None) == "spaghetti pasta"

    def test_empty_brand(self):
        assert _clean_search_name("Spaghetti Pasta", "") == "spaghetti pasta"

    def test_embedded_size_removed(self):
        assert _clean_search_name("Spaghetti 500g", None) == "spaghetti"

    def test_embedded_size_litres(self):
        assert _clean_search_name("Milk 2l Homogenised", None) == "milk homogenised"

    def test_multipack_size_removed(self):
        assert _clean_search_name("Beer 6 x 330ml Lager", None) == "beer lager"

    def test_brand_and_size_both_removed(self):
        result = _clean_search_name("Woolworths Pasta 500g Spaghetti", "Woolworths")
        assert result == "pasta spaghetti"

    def test_only_brand_and_size(self):
        """Edge case: name is just brand + size."""
        result = _clean_search_name("Woolworths 500g", "Woolworths")
        assert result == ""


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


class TestEffectivePriceLoyalty:
    """Tests for _effective_price with loyalty card awareness."""

    def test_member_promo_with_card(self):
        """Member-only promo with loyalty card → returns promo price."""
        result = _effective_price(
            price_nzd=10.0,
            promo_price_nzd=7.0,
            promo_ends_at=None,
            is_member_only=True,
            has_loyalty_card=True,
        )
        assert result == 7.0

    def test_member_promo_without_card(self):
        """Member-only promo without loyalty card → returns regular price."""
        result = _effective_price(
            price_nzd=10.0,
            promo_price_nzd=7.0,
            promo_ends_at=None,
            is_member_only=True,
            has_loyalty_card=False,
        )
        assert result == 10.0

    def test_regular_promo_without_card(self):
        """Non-member promo without loyalty card → still returns promo price."""
        result = _effective_price(
            price_nzd=10.0,
            promo_price_nzd=8.0,
            promo_ends_at=None,
            is_member_only=False,
            has_loyalty_card=False,
        )
        assert result == 8.0

    def test_no_promo(self):
        """No promo → returns regular price regardless of card."""
        result = _effective_price(
            price_nzd=10.0,
            promo_price_nzd=None,
            promo_ends_at=None,
            is_member_only=False,
            has_loyalty_card=True,
        )
        assert result == 10.0

    def test_default_has_card(self):
        """Default has_loyalty_card=True → member promo applies."""
        result = _effective_price(
            price_nzd=10.0,
            promo_price_nzd=6.0,
            promo_ends_at=None,
            is_member_only=True,
        )
        assert result == 6.0


class TestTrolleySchemaLoyaltyCards:
    """Tests for loyalty_cards in TrolleyCompareRequest."""

    def test_request_with_loyalty_cards(self):
        req = TrolleyCompareRequest(
            items=[TrolleyItem(product_id=uuid.uuid4(), quantity=1)],
            lat=-36.8485,
            lon=174.7633,
            radius_km=5,
            loyalty_cards={"countdown": False, "paknsave": True},
        )
        assert req.loyalty_cards["countdown"] is False
        assert req.loyalty_cards["paknsave"] is True

    def test_request_without_loyalty_cards(self):
        req = TrolleyCompareRequest(
            items=[TrolleyItem(product_id=uuid.uuid4(), quantity=1)],
            lat=-36.8485,
            lon=174.7633,
            radius_km=5,
        )
        assert req.loyalty_cards is None
