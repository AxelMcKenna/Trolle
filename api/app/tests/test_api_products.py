"""Tests for products API endpoints."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestListProductsEndpoint:
    """Tests for GET /products endpoint."""

    def test_products_requires_location_for_non_promo(self, client: TestClient):
        """Products endpoint should require location for non-promo queries."""
        response = client.get("/products")
        assert response.status_code == 400
        assert "Location parameters" in response.json()["detail"]

    def test_products_promo_only_no_location_ok(self, client: TestClient):
        """Small promo-only queries should work without location."""
        mock_response = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20
        }

        with patch("app.routes.products.fetch_products", AsyncMock(return_value=type(
            "MockResponse", (), {"json": lambda self: '{"items":[],"total":0,"page":1,"page_size":20}'}
        )())):
            with patch("app.routes.products.cached_json", AsyncMock(return_value=mock_response)):
                response = client.get("/products?promo_only=true&page_size=10")

        assert response.status_code == 200

    def test_products_validates_nz_location(self, client: TestClient):
        """Products should reject locations outside New Zealand."""
        response = client.get("/products?lat=-33.8688&lon=151.2093&radius_km=10")
        assert response.status_code == 400
        assert "New Zealand" in response.json()["detail"]

    def test_products_validates_max_radius(self, client: TestClient):
        """Products should reject radius > 10km."""
        response = client.get("/products?lat=-36.8485&lon=174.7633&radius_km=11")
        assert response.status_code in [400, 422]

    def test_products_valid_nz_location(self, client: TestClient):
        """Products should accept valid NZ location."""
        mock_response = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20
        }

        with patch("app.routes.products.cached_json", AsyncMock(return_value=mock_response)):
            response = client.get("/products?lat=-36.8485&lon=174.7633&radius_km=10")

        assert response.status_code == 200

    def test_products_query_params(self, client: TestClient):
        """Products endpoint should accept various query parameters."""
        mock_response = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 10
        }

        with patch("app.routes.products.cached_json", AsyncMock(return_value=mock_response)):
            response = client.get(
                "/products"
                "?lat=-36.8485&lon=174.7633&radius_km=10"
                "&q=milk"
                "&chain=countdown,paknsave"
                "&category=Milk"
                "&price_min=1&price_max=20"
                "&promo_only=true"
                "&sort=total_price"
                "&page=1&page_size=10"
            )

        assert response.status_code == 200

    def test_products_supports_repeated_chain_params(self, client: TestClient):
        """Products should parse repeated chain params like chain=a&chain=b."""
        mock_response = {"items": [], "total": 0, "page": 1, "page_size": 20}

        async def check_cache_key(cache_key: str, *_args):
            parsed = json.loads(cache_key)
            assert parsed["chain"] == ["countdown", "paknsave"]
            return mock_response

        with patch("app.routes.products.cached_json", AsyncMock(side_effect=check_cache_key)):
            response = client.get(
                "/products"
                "?lat=-36.8485&lon=174.7633&radius_km=5"
                "&chain=countdown&chain=paknsave"
            )

        assert response.status_code == 200

    def test_products_distance_sort_requires_location(self, client: TestClient):
        """Distance sort should return 422 when location is missing."""
        response = client.get("/products?promo_only=true&sort=distance&page_size=10")
        assert response.status_code == 422

    def test_products_invalid_store_uuid_rejected(self, client: TestClient):
        """Invalid store IDs should fail validation."""
        response = client.get(
            "/products?lat=-36.8485&lon=174.7633&radius_km=5&store=not-a-uuid"
        )
        assert response.status_code == 422

    def test_products_response_structure(self, client: TestClient):
        """Products response should have correct structure."""
        mock_response = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20
        }

        with patch("app.routes.products.cached_json", AsyncMock(return_value=mock_response)):
            response = client.get("/products?lat=-36.8485&lon=174.7633&radius_km=10")

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)

    def test_products_edge_of_nz_bounds(self, client: TestClient):
        """Products should accept locations at edge of NZ bounds."""
        mock_response = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20
        }

        with patch("app.routes.products.cached_json", AsyncMock(return_value=mock_response)):
            response = client.get("/products?lat=-46.6&lon=168.3&radius_km=10")

        assert response.status_code == 200


class TestProductDetailEndpoint:
    """Tests for GET /products/{product_id} endpoint."""

    def test_product_detail_not_found(self, client: TestClient):
        """Product detail should return 404 for non-existent product."""
        import uuid

        with patch("app.routes.products.fetch_product_detail",
                   AsyncMock(side_effect=ValueError("Product not found"))):
            response = client.get(f"/products/{uuid.uuid4()}")

        assert response.status_code == 404

    def test_product_detail_invalid_uuid(self, client: TestClient):
        """Product detail should return 422 for invalid UUID."""
        response = client.get("/products/not-a-uuid")
        assert response.status_code == 422

    def test_product_detail_success(self, client: TestClient):
        """Product detail should return product data."""
        import uuid
        from datetime import datetime
        from app.schemas.products import ProductDetailSchema, PriceSchema

        product_id = uuid.uuid4()
        store_id = uuid.uuid4()

        mock_price = PriceSchema(
            store_id=store_id,
            store_name="Test Store",
            chain="countdown",
            price_nzd=5.49,
            promo_price_nzd=None,
            promo_text=None,
            promo_ends_at=None,
            unit_price=2.75,
            unit_measure="1L",
            is_member_only=False,
            distance_km=None,
        )

        mock_product = ProductDetailSchema(
            id=product_id,
            name="Anchor Blue Top Milk 2L",
            brand="Anchor",
            category="Milk",
            chain="countdown",
            size="2L",
            department="Chilled, Dairy & Eggs",
            subcategory="Milk",
            image_url=None,
            product_url=None,
            description=None,
            price=mock_price,
            last_updated=datetime.utcnow(),
        )

        with patch("app.routes.products.fetch_product_detail", AsyncMock(return_value=mock_product)):
            response = client.get(f"/products/{product_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Anchor Blue Top Milk 2L"
        assert data["brand"] == "Anchor"
        assert data["size"] == "2L"
        assert data["department"] == "Chilled, Dairy & Eggs"


class TestProductsLocationValidation:
    """Tests for location validation edge cases."""

    def test_lat_out_of_range_north(self, client: TestClient):
        """Latitude north of NZ should be rejected."""
        response = client.get("/products?lat=-30.0&lon=174.7633&radius_km=10")
        assert response.status_code == 400

    def test_lat_out_of_range_south(self, client: TestClient):
        """Latitude south of NZ should be rejected."""
        response = client.get("/products?lat=-50.0&lon=174.7633&radius_km=10")
        assert response.status_code == 400

    def test_lon_out_of_range_west(self, client: TestClient):
        """Longitude west of NZ should be rejected."""
        response = client.get("/products?lat=-36.8485&lon=160.0&radius_km=10")
        assert response.status_code == 400

    def test_lon_out_of_range_east(self, client: TestClient):
        """Longitude east of NZ should be rejected."""
        response = client.get("/products?lat=-36.8485&lon=180.0&radius_km=10")
        assert response.status_code == 400

    def test_zero_radius_rejected(self, client: TestClient):
        """Zero radius should be rejected by validation."""
        response = client.get("/products?lat=-36.8485&lon=174.7633&radius_km=0")
        assert response.status_code in [400, 422]

    def test_negative_radius_rejected(self, client: TestClient):
        """Negative radius should be rejected."""
        response = client.get("/products?lat=-36.8485&lon=174.7633&radius_km=-10")
        assert response.status_code in [400, 422]

    def test_radius_below_minimum(self, client: TestClient):
        """Radius below 1km should be rejected."""
        response = client.get("/products?lat=-36.8485&lon=174.7633&radius_km=0.5")
        assert response.status_code in [400, 422]
