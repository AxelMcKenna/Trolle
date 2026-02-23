"""Tests for store category rankings."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestUnionFind:
    """Tests for the UnionFind data structure."""

    def test_separate_groups(self):
        from app.services.rankings import UnionFind

        uf = UnionFind()
        uf.find("a")
        uf.find("b")
        uf.find("c")
        groups = uf.groups()
        assert len(groups) == 3

    def test_union_merges(self):
        from app.services.rankings import UnionFind

        uf = UnionFind()
        uf.union("a", "b")
        groups = uf.groups()
        assert len(groups) == 1
        assert sorted(list(groups.values())[0]) == ["a", "b"]

    def test_transitive_merge(self):
        from app.services.rankings import UnionFind

        uf = UnionFind()
        uf.union("a", "b")
        uf.union("b", "c")
        groups = uf.groups()
        assert len(groups) == 1
        assert sorted(list(groups.values())[0]) == ["a", "b", "c"]

    def test_separate_and_merged(self):
        from app.services.rankings import UnionFind

        uf = UnionFind()
        uf.union("a", "b")
        uf.find("c")
        groups = uf.groups()
        assert len(groups) == 2

    def test_tuple_keys(self):
        from app.services.rankings import UnionFind

        uf = UnionFind()
        uf.union(("countdown", "ABC"), ("paknsave", "XYZ"))
        groups = uf.groups()
        assert len(groups) == 1


class TestComputeRankings:
    """Tests for the _compute_rankings function."""

    def _make_store_info(self, store_ids):
        return {
            sid: {"name": f"Store {i}", "chain": "countdown", "distance_km": float(i), "total_products": 10}
            for i, sid in enumerate(store_ids)
        }

    def test_basic_price_index(self):
        from app.services.rankings import _compute_rankings

        s1, s2 = uuid.uuid4(), uuid.uuid4()
        store_info = self._make_store_info([s1, s2])

        # Product A: s1=$5, s2=$10 → ratios: s1=1.0, s2=2.0
        groups = [[(s1, 5.0), (s2, 10.0)]]
        ranked = _compute_rankings(store_info, groups)

        idx = {r.store_id: r for r in ranked}
        assert idx[s1].price_index == 100.0
        assert idx[s2].price_index == 200.0

    def test_multiple_groups_average(self):
        from app.services.rankings import _compute_rankings

        s1, s2 = uuid.uuid4(), uuid.uuid4()
        store_info = self._make_store_info([s1, s2])

        # Group 1: s1=$5, s2=$10 → ratios: s1=1.0, s2=2.0
        # Group 2: s1=$8, s2=$4 → ratios: s1=2.0, s2=1.0
        # Average: s1=1.5→150, s2=1.5→150
        groups = [
            [(s1, 5.0), (s2, 10.0)],
            [(s1, 8.0), (s2, 4.0)],
        ]
        ranked = _compute_rankings(store_info, groups)
        idx = {r.store_id: r for r in ranked}
        assert idx[s1].price_index == 150.0
        assert idx[s2].price_index == 150.0

    def test_cheapest_count(self):
        from app.services.rankings import _compute_rankings

        s1, s2 = uuid.uuid4(), uuid.uuid4()
        store_info = self._make_store_info([s1, s2])

        groups = [
            [(s1, 3.0), (s2, 5.0)],
            [(s1, 2.0), (s2, 4.0)],
            [(s1, 7.0), (s2, 6.0)],
        ]
        ranked = _compute_rankings(store_info, groups)
        idx = {r.store_id: r for r in ranked}
        assert idx[s1].cheapest_count == 2
        assert idx[s2].cheapest_count == 1

    def test_tie_in_cheapest(self):
        from app.services.rankings import _compute_rankings

        s1, s2 = uuid.uuid4(), uuid.uuid4()
        store_info = self._make_store_info([s1, s2])

        # Both stores at same price
        groups = [[(s1, 5.0), (s2, 5.0)]]
        ranked = _compute_rankings(store_info, groups)
        idx = {r.store_id: r for r in ranked}
        assert idx[s1].cheapest_count == 1
        assert idx[s2].cheapest_count == 1
        assert idx[s1].price_index == 100.0

    def test_store_with_no_matches(self):
        from app.services.rankings import _compute_rankings

        s1, s2, s3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        store_info = self._make_store_info([s1, s2, s3])

        # Only s1 and s2 have comparable products
        groups = [[(s1, 5.0), (s2, 10.0)]]
        ranked = _compute_rankings(store_info, groups)
        idx = {r.store_id: r for r in ranked}
        assert idx[s3].price_index == 0.0
        assert idx[s3].matched_products == 0
        # Unmatched stores sort after matched stores
        assert ranked[-1].store_id == s3

    def test_single_store_group_skipped(self):
        from app.services.rankings import _compute_rankings

        s1 = uuid.uuid4()
        store_info = self._make_store_info([s1])

        # Only one store in group — cannot compare
        groups = [[(s1, 5.0)]]
        ranked = _compute_rankings(store_info, groups)
        assert ranked[0].matched_products == 0
        assert ranked[0].price_index == 0.0

    def test_empty_groups(self):
        from app.services.rankings import _compute_rankings

        s1 = uuid.uuid4()
        store_info = self._make_store_info([s1])
        ranked = _compute_rankings(store_info, [])
        assert len(ranked) == 1
        assert ranked[0].price_index == 0.0


class TestRankingsEndpointValidation:
    """Tests for GET /stores/rankings parameter validation."""

    def test_missing_category(self, client: TestClient):
        response = client.get("/stores/rankings?lat=-36.8485&lon=174.7633")
        assert response.status_code == 422

    def test_missing_lat(self, client: TestClient):
        response = client.get("/stores/rankings?category=Pantry&lon=174.7633")
        assert response.status_code == 422

    def test_missing_lon(self, client: TestClient):
        response = client.get("/stores/rankings?category=Pantry&lat=-36.8485")
        assert response.status_code == 422

    def test_invalid_category(self, client: TestClient):
        response = client.get("/stores/rankings?category=NotACategory&lat=-36.8485&lon=174.7633")
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]

    def test_lat_out_of_nz_bounds(self, client: TestClient):
        response = client.get("/stores/rankings?category=Pantry&lat=0&lon=174.7633")
        assert response.status_code == 400
        assert "Latitude" in response.json()["detail"]

    def test_lon_out_of_nz_bounds(self, client: TestClient):
        response = client.get("/stores/rankings?category=Pantry&lat=-36.8485&lon=0")
        assert response.status_code == 400
        assert "Longitude" in response.json()["detail"]

    def test_radius_exceeds_max(self, client: TestClient):
        response = client.get("/stores/rankings?category=Pantry&lat=-36.8485&lon=174.7633&radius_km=15")
        assert response.status_code == 400
        assert "10km" in response.json()["detail"]

    def test_radius_zero_rejected(self, client: TestClient):
        response = client.get("/stores/rankings?category=Pantry&lat=-36.8485&lon=174.7633&radius_km=0")
        assert response.status_code == 400

    def test_radius_negative_rejected(self, client: TestClient):
        response = client.get("/stores/rankings?category=Pantry&lat=-36.8485&lon=174.7633&radius_km=-5")
        assert response.status_code == 400


class TestRankingsEndpointSuccess:
    """Tests for GET /stores/rankings with mocked service."""

    def test_success_response(self, client: TestClient):
        from app.schemas.rankings import StoreRankingResponse

        mock_response = StoreRankingResponse(
            category="Pantry",
            stores=[],
            total_comparison_products=0,
        )

        with patch(
            "app.routes.stores.rank_stores_by_category",
            AsyncMock(return_value=mock_response),
        ):
            response = client.get("/stores/rankings?category=Pantry&lat=-36.8485&lon=174.7633")

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "Pantry"
        assert isinstance(data["stores"], list)
        assert data["total_comparison_products"] == 0

    def test_success_with_stores(self, client: TestClient):
        from app.schemas.rankings import RankedStore, StoreRankingResponse

        store_id = uuid.uuid4()
        mock_response = StoreRankingResponse(
            category="Pantry",
            stores=[
                RankedStore(
                    store_id=store_id,
                    store_name="PAK'nSAVE Albany",
                    chain="paknsave",
                    distance_km=2.1,
                    price_index=100.0,
                    matched_products=25,
                    total_category_products=40,
                    avg_effective_price=4.50,
                    cheapest_count=15,
                ),
            ],
            total_comparison_products=25,
        )

        with patch(
            "app.routes.stores.rank_stores_by_category",
            AsyncMock(return_value=mock_response),
        ):
            response = client.get("/stores/rankings?category=Pantry&lat=-36.8485&lon=174.7633&radius_km=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data["stores"]) == 1
        store = data["stores"][0]
        assert store["store_name"] == "PAK'nSAVE Albany"
        assert store["price_index"] == 100.0
        assert store["matched_products"] == 25

    def test_default_radius(self, client: TestClient):
        from app.schemas.rankings import StoreRankingResponse

        mock_response = StoreRankingResponse(category="Pantry", stores=[], total_comparison_products=0)
        mock_fn = AsyncMock(return_value=mock_response)

        with patch("app.routes.stores.rank_stores_by_category", mock_fn):
            client.get("/stores/rankings?category=Pantry&lat=-36.8485&lon=174.7633")

        # Default radius_km is 5.0
        assert mock_fn.call_args.args[3] == 174.7633  # lon
        assert mock_fn.call_args.args[4] == 5.0  # radius_km


class TestValidCategories:
    """Tests for VALID_CATEGORIES list."""

    def test_known_categories_present(self):
        from app.services.rankings import VALID_CATEGORIES

        assert "Pantry" in VALID_CATEGORIES
        assert "Meat & Seafood" in VALID_CATEGORIES
        assert "Frozen" in VALID_CATEGORIES
        assert "Drinks" in VALID_CATEGORIES

    def test_subcategories_not_present(self):
        from app.services.rankings import VALID_CATEGORIES

        assert "Pasta, Rice & Noodles" not in VALID_CATEGORIES
        assert "Milk" not in VALID_CATEGORIES
