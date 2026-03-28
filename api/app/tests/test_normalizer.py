"""Tests for product normalization utilities."""
import pytest

from app.services.normalizer import (
    StructuredSize,
    brands_equivalent,
    clean_product_name,
    extract_size_from_text,
    normalize_brand,
    parse_structured_size,
    sizes_equivalent,
)


# ---------------------------------------------------------------------------
# parse_structured_size
# ---------------------------------------------------------------------------

class TestParseStructuredSize:
    """Tests for size string parsing."""

    # -- Simple volume --
    def test_simple_ml(self):
        s = parse_structured_size("330ml")
        assert s.volume_ml == 330.0
        assert s.weight_g is None
        assert s.size_type == "volume"

    def test_simple_litres(self):
        s = parse_structured_size("1.5L")
        assert s.volume_ml == 1500.0
        assert s.size_type == "volume"

    def test_simple_litres_long(self):
        s = parse_structured_size("2 Litres")
        assert s.volume_ml == 2000.0

    def test_simple_cl(self):
        s = parse_structured_size("75cl")
        assert s.volume_ml == 750.0

    # -- Simple weight --
    def test_simple_grams(self):
        s = parse_structured_size("500g")
        assert s.weight_g == 500.0
        assert s.volume_ml is None
        assert s.size_type == "weight"

    def test_simple_kg(self):
        s = parse_structured_size("1.5kg")
        assert s.weight_g == 1500.0

    def test_simple_grams_long(self):
        s = parse_structured_size("250 Grams")
        assert s.weight_g == 250.0

    # -- Multipacks --
    def test_multipack_volume(self):
        s = parse_structured_size("6 x 330ml")
        assert s.pack_count == 6
        assert s.unit_volume_ml == 330.0
        assert s.volume_ml == 1980.0
        assert s.size_type == "volume"

    def test_multipack_no_spaces(self):
        s = parse_structured_size("4x250g")
        assert s.pack_count == 4
        assert s.unit_weight_g == 250.0
        assert s.weight_g == 1000.0

    def test_multipack_X_uppercase(self):
        s = parse_structured_size("12 X 355 ML")
        assert s.pack_count == 12
        assert s.volume_ml == pytest.approx(4260.0)

    def test_multipack_times_sign(self):
        s = parse_structured_size("6×330ml")
        assert s.pack_count == 6
        assert s.volume_ml == 1980.0

    # -- Pack + size --
    def test_pack_with_size(self):
        s = parse_structured_size("6 Pack 330ml Cans")
        assert s.pack_count == 6
        assert s.unit_volume_ml == 330.0
        assert s.volume_ml == 1980.0

    def test_pack_with_weight(self):
        s = parse_structured_size("12pk 25g")
        assert s.pack_count == 12
        assert s.unit_weight_g == 25.0
        assert s.weight_g == 300.0

    # -- Weight ranges --
    def test_weight_range(self):
        s = parse_structured_size("1kg-1.5kg")
        assert s.weight_g == pytest.approx(1250.0)
        assert s.size_type == "weight"

    def test_weight_range_grams(self):
        s = parse_structured_size("500g - 700g")
        assert s.weight_g == pytest.approx(600.0)

    # -- Pack count only --
    def test_pack_only(self):
        s = parse_structured_size("6 Pack")
        assert s.pack_count == 6
        assert s.volume_ml is None
        assert s.weight_g is None
        assert s.size_type == "count"

    def test_pk_only(self):
        s = parse_structured_size("12pk")
        assert s.pack_count == 12
        assert s.size_type == "count"

    # -- Per-unit --
    def test_each(self):
        s = parse_structured_size("each")
        assert s.size_type == "each"

    def test_ea(self):
        s = parse_structured_size("ea")
        assert s.size_type == "each"

    # -- Edge cases --
    def test_empty_string(self):
        s = parse_structured_size("")
        assert s.size_type == "unknown"
        assert s.volume_ml is None
        assert s.weight_g is None

    def test_no_size_info(self):
        s = parse_structured_size("Bananas")
        assert s.size_type == "unknown"

    def test_size_in_product_name(self):
        s = parse_structured_size("Anchor Blue Milk 2L")
        assert s.volume_ml == 2000.0

    def test_multipack_in_name(self):
        s = parse_structured_size("Heineken Lager 6 x 330ml Cans")
        assert s.pack_count == 6
        assert s.volume_ml == 1980.0


# ---------------------------------------------------------------------------
# extract_size_from_text
# ---------------------------------------------------------------------------

class TestExtractSizeFromText:
    def test_simple_at_end(self):
        assert extract_size_from_text("Original Crunchy 375g") == "375g"

    def test_simple_volume(self):
        assert extract_size_from_text("2L") == "2L"

    def test_size_in_middle(self):
        assert extract_size_from_text("Smooth 500g Jar") == "500g"

    def test_multipack(self):
        result = extract_size_from_text("6 x 330ml Cans")
        assert result == "6 x 330ml"

    def test_no_size(self):
        assert extract_size_from_text("Bananas") is None

    def test_empty(self):
        assert extract_size_from_text("") is None

    def test_none(self):
        assert extract_size_from_text(None) is None

    def test_pack_only(self):
        assert extract_size_from_text("6 Pack") == "6 Pack"


# ---------------------------------------------------------------------------
# sizes_equivalent
# ---------------------------------------------------------------------------

class TestSizesEquivalent:
    def test_same_volume(self):
        a = StructuredSize(volume_ml=1500.0, size_type="volume")
        b = StructuredSize(volume_ml=1500.0, size_type="volume")
        assert sizes_equivalent(a, b) is True

    def test_equivalent_volume(self):
        """1.5L == 1500ml (both parsed to 1500ml)."""
        a = parse_structured_size("1.5L")
        b = parse_structured_size("1500ml")
        assert sizes_equivalent(a, b) is True

    def test_different_volume(self):
        a = StructuredSize(volume_ml=330.0, size_type="volume")
        b = StructuredSize(volume_ml=1980.0, size_type="volume")
        assert sizes_equivalent(a, b) is False

    def test_same_weight(self):
        a = StructuredSize(weight_g=500.0, size_type="weight")
        b = StructuredSize(weight_g=500.0, size_type="weight")
        assert sizes_equivalent(a, b) is True

    def test_different_weight(self):
        a = StructuredSize(weight_g=500.0, size_type="weight")
        b = StructuredSize(weight_g=1000.0, size_type="weight")
        assert sizes_equivalent(a, b) is False

    def test_within_tolerance(self):
        a = StructuredSize(weight_g=500.0, size_type="weight")
        b = StructuredSize(weight_g=505.0, size_type="weight")
        assert sizes_equivalent(a, b, tolerance=0.02) is True

    def test_pack_count_only(self):
        a = StructuredSize(pack_count=6, size_type="count")
        b = StructuredSize(pack_count=6, size_type="count")
        assert sizes_equivalent(a, b) is True

    def test_different_pack_count(self):
        a = StructuredSize(pack_count=6, size_type="count")
        b = StructuredSize(pack_count=12, size_type="count")
        assert sizes_equivalent(a, b) is False

    def test_both_each(self):
        a = StructuredSize(size_type="each")
        b = StructuredSize(size_type="each")
        assert sizes_equivalent(a, b) is True

    def test_incomparable(self):
        """Volume vs weight → can't compare."""
        a = StructuredSize(volume_ml=500.0, size_type="volume")
        b = StructuredSize(weight_g=500.0, size_type="weight")
        assert sizes_equivalent(a, b) is None

    def test_both_unknown(self):
        a = StructuredSize(size_type="unknown")
        b = StructuredSize(size_type="unknown")
        assert sizes_equivalent(a, b) is None

    def test_multipack_vs_single(self):
        """6x330ml (1980ml) should NOT match 330ml."""
        a = parse_structured_size("6 x 330ml")
        b = parse_structured_size("330ml")
        assert sizes_equivalent(a, b) is False


# ---------------------------------------------------------------------------
# Brand normalization
# ---------------------------------------------------------------------------

class TestBrandNormalization:
    def test_normalize_brand(self):
        assert normalize_brand("  Anchor  ") == "anchor"
        assert normalize_brand("WOOLWORTHS") == "woolworths"

    def test_same_brand(self):
        assert brands_equivalent("Anchor", "Anchor") is True

    def test_case_insensitive(self):
        assert brands_equivalent("anchor", "ANCHOR") is True

    def test_own_brand_same_group(self):
        assert brands_equivalent("Woolworths", "Countdown") is True

    def test_own_brand_pams(self):
        assert brands_equivalent("Pams", "Pams Finest") is True

    def test_different_brands(self):
        assert brands_equivalent("Anchor", "Meadow Fresh") is False

    def test_own_brand_vs_real_brand(self):
        assert brands_equivalent("Woolworths", "Anchor") is False

    def test_none_brand(self):
        assert brands_equivalent(None, "Anchor") is False
        assert brands_equivalent("Anchor", None) is False

    def test_empty_brand(self):
        assert brands_equivalent("", "Anchor") is False


# ---------------------------------------------------------------------------
# Name cleaning
# ---------------------------------------------------------------------------

class TestCleanProductName:
    def test_strips_brand(self):
        result = clean_product_name("Woolworths Spaghetti 500g", "Woolworths")
        assert "woolworths" not in result
        assert "spaghetti" in result

    def test_strips_size(self):
        result = clean_product_name("Anchor Milk 2L", "Anchor")
        assert "2l" not in result
        assert "milk" in result

    def test_strips_multipack_size(self):
        result = clean_product_name("Heineken 6 x 330ml Cans", "Heineken")
        assert "330ml" not in result
        assert "cans" in result

    def test_strips_noise_words(self):
        result = clean_product_name("Fresh Premium Chicken Breast", None)
        assert "fresh" not in result
        assert "premium" not in result
        assert "chicken" in result
        assert "breast" in result

    def test_no_brand(self):
        result = clean_product_name("Free Range Eggs 12 Pack", None)
        assert "eggs" in result

    def test_normalizes_whitespace(self):
        result = clean_product_name("  Anchor   Blue   Milk  2L ", "Anchor")
        assert "  " not in result

    def test_multiple_brand_occurrences(self):
        result = clean_product_name(
            "Woolworths Spaghetti Woolworths Pasta", "Woolworths"
        )
        assert "woolworths" not in result
        assert "spaghetti" in result
        assert "pasta" in result
