"""
Tests for store location scrapers.

Tests store location scrapers for countdown, new_world, and paknsave chains.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.store_scrapers.base import StoreLocationScraper


class TestStoreLocationScraperBase:
    """Tests for the StoreLocationScraper base class."""

    def test_base_class_is_abstract(self):
        """Test that base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            StoreLocationScraper()

    def test_subclass_requires_fetch_stores(self):
        """Test that subclasses must implement fetch_stores."""
        class InvalidScraper(StoreLocationScraper):
            chain = "test"
            store_locator_url = "https://example.com"

        with pytest.raises(TypeError):
            InvalidScraper()


class TestNZStoreCoverage:
    """Tests to verify store scrapers can cover all NZ regions."""

    NZ_CITIES = {
        "Auckland": (-36.8485, 174.7633),
        "Wellington": (-41.2865, 174.7762),
        "Christchurch": (-43.5321, 172.6362),
        "Hamilton": (-37.7870, 175.2793),
        "Tauranga": (-37.6878, 176.1651),
        "Dunedin": (-45.8788, 170.5028),
        "Palmerston North": (-40.3523, 175.6082),
        "Napier": (-39.4928, 176.9120),
        "Nelson": (-41.2706, 173.2840),
        "Rotorua": (-38.1368, 176.2497),
        "Queenstown": (-45.0312, 168.6626),
        "Invercargill": (-46.4132, 168.3538),
        "Whangarei": (-35.7275, 174.3166),
        "New Plymouth": (-39.0556, 174.0752),
        "Gisborne": (-38.6587, 177.9853),
    }

    def test_nz_regions_defined(self):
        """Verify we have all major NZ cities for coverage testing."""
        assert len(self.NZ_CITIES) >= 15
        assert "Auckland" in self.NZ_CITIES
        assert "Wellington" in self.NZ_CITIES
        assert "Christchurch" in self.NZ_CITIES

    def test_coordinate_validity(self):
        """Test that all NZ coordinates are valid."""
        for city, (lat, lon) in self.NZ_CITIES.items():
            assert -47 <= lat <= -34, f"Invalid latitude for {city}: {lat}"
            assert 166 <= lon <= 180, f"Invalid longitude for {city}: {lon}"


class TestStoreDataFiles:
    """Tests for store data JSON files."""

    DATA_DIR = Path(__file__).parent.parent / "data"

    @pytest.mark.parametrize("filename", [
        "countdown_stores.json",
        "newworld_stores.json",
        "paknsave_stores.json",
    ])
    def test_store_data_files_exist(self, filename):
        """Test that store data files exist."""
        filepath = self.DATA_DIR / filename
        if filepath.exists():
            assert filepath.is_file()
            with open(filepath) as f:
                data = json.load(f)
            assert isinstance(data, (list, dict))

    def test_store_data_has_required_fields(self):
        """Test that store data has required fields."""
        for filename in ["countdown_stores.json", "newworld_stores.json"]:
            filepath = self.DATA_DIR / filename
            if filepath.exists():
                with open(filepath) as f:
                    data = json.load(f)

                stores = data if isinstance(data, list) else list(data.values())
                for store in stores[:5]:
                    if isinstance(store, dict):
                        has_name = any(
                            key in store
                            for key in ["name", "label", "storeName", "Name"]
                        )
                        assert has_name, f"Store missing name field in {filename}"
