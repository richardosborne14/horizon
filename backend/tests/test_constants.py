"""
Unit tests for inflation scales and growth presets (TASK 1.3).

Tests cover:
- get_growth_rate returns correct values for each preset
- Custom preset with and without custom_rate
- Invalid preset raises ValueError
- All inflation scales have required fields
- All values are Decimal, never float
"""

from decimal import Decimal

import pytest

from app.calculations.constants import (
    get_growth_rate,
    get_inflation_scale,
    INFLATION_SCALES,
    GROWTH_PRESETS,
)


class TestGetGrowthRate:
    """Tests for get_growth_rate() — resolving a preset key to a rate."""

    def test_conservative(self):
        rate = get_growth_rate("conservative")
        assert rate == Decimal("0.01")

    def test_moderate(self):
        rate = get_growth_rate("moderate")
        assert rate == Decimal("0.03")

    def test_ambitious(self):
        rate = get_growth_rate("ambitious")
        assert rate == Decimal("0.06")

    def test_custom_with_rate(self):
        """Custom preset with explicit rate should return that rate."""
        rate = get_growth_rate("custom", Decimal("0.05"))
        assert rate == Decimal("0.05")

    def test_custom_without_rate_fallback(self):
        """Custom preset without rate falls back to moderate (0.03)."""
        rate = get_growth_rate("custom", None)
        assert rate == Decimal("0.03")

    def test_custom_with_zero(self):
        """Custom rate of 0 should work (stable income)."""
        rate = get_growth_rate("custom", Decimal("0"))
        assert rate == Decimal("0")

    def test_unknown_preset_raises_valueerror(self):
        """Invalid preset should raise ValueError with helpful message."""
        with pytest.raises(ValueError) as exc_info:
            get_growth_rate("rocket")
        assert "Unknown growth preset" in str(exc_info.value)
        assert "rocket" in str(exc_info.value)

    def test_all_returns_are_decimal(self):
        """Every path should return a Decimal, never a float."""
        for preset in ["conservative", "moderate", "ambitious"]:
            rate = get_growth_rate(preset)
            assert isinstance(rate, Decimal), (
                f"get_growth_rate({preset!r}) returned "
                f"{type(rate).__name__}, expected Decimal"
            )

        # Custom with rate
        rate = get_growth_rate("custom", Decimal("0.07"))
        assert isinstance(rate, Decimal)

        # Custom without rate
        rate = get_growth_rate("custom", None)
        assert isinstance(rate, Decimal)


class TestGetInflationScale:
    """Tests for get_inflation_scale()."""

    def test_valid_scales(self):
        """Each scale key should return a valid dict."""
        for scale_key in ["optimistic", "moderate", "pessimistic"]:
            scale = get_inflation_scale(scale_key)
            assert isinstance(scale, dict)
            assert "label" in scale
            assert "inflation" in scale
            assert "cost_living" in scale

    def test_unknown_scale_raises_valueerror(self):
        """Invalid scale should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_inflation_scale("apocalyptic")
        assert "Unknown inflation scale" in str(exc_info.value)

    def test_rates_are_decimal(self):
        """Inflation and cost_living values must be Decimal."""
        for scale in INFLATION_SCALES.values():
            assert isinstance(scale["inflation"], Decimal)
            assert isinstance(scale["cost_living"], Decimal)

    def test_moderate_is_default(self):
        """The moderate scale should be 2.5% inflation, 3.0% cost_living."""
        scale = get_inflation_scale("moderate")
        assert scale["inflation"] == Decimal("0.025")
        assert scale["cost_living"] == Decimal("0.030")


class TestGrowthPresetsStructure:
    """Verify the GROWTH_PRESETS dict is well-formed."""

    def test_all_required_keys_present(self):
        """Each preset should have label, rate, description."""
        for key, preset in GROWTH_PRESETS.items():
            assert "label" in preset, f"Missing 'label' in {key}"
            assert "rate" in preset, f"Missing 'rate' in {key}"
            assert "description" in preset, f"Missing 'description' in {key}"

    def test_non_custom_presets_have_rate(self):
        """All presets except 'custom' should have a non-None rate."""
        for key, preset in GROWTH_PRESETS.items():
            if key != "custom":
                assert preset["rate"] is not None, (
                    f"Preset {key!r} should have a defined rate"
                )
                assert isinstance(preset["rate"], Decimal)
                assert preset["rate"] > Decimal("0"), (
                    f"Preset {key!r} rate should be positive"
                )

    def test_custom_has_none_rate(self):
        """Custom preset's rate is None (user provides it)."""
        assert GROWTH_PRESETS["custom"]["rate"] is None


class TestInflationScalesStructure:
    """Verify the INFLATION_SCALES dict is well-formed."""

    def test_all_required_keys(self):
        """Each scale must have label, emoji, inflation, cost_living,
        description, color."""
        required_keys = {
            "label", "emoji", "inflation", "cost_living",
            "description", "color",
        }
        for key, scale in INFLATION_SCALES.items():
            missing = required_keys - set(scale.keys())
            assert not missing, (
                f"Scale {key!r} missing keys: {missing}"
            )

    def test_inflation_less_than_cost_living(self):
        """Cost of living growth should be higher than general inflation
        (reflects lifestyle creep)."""
        for key, scale in INFLATION_SCALES.items():
            assert scale["cost_living"] >= scale["inflation"], (
                f"Scale {key!r}: cost_living ({scale['cost_living']}) < "
                f"inflation ({scale['inflation']})"
            )

    def test_optimistic_lowest_pessimistic_highest(self):
        """Rates should increase from optimistic → moderate → pessimistic."""
        opt_inf = INFLATION_SCALES["optimistic"]["inflation"]
        mod_inf = INFLATION_SCALES["moderate"]["inflation"]
        pes_inf = INFLATION_SCALES["pessimistic"]["inflation"]
        assert opt_inf < mod_inf < pes_inf, (
            f"Expected {opt_inf} < {mod_inf} < {pes_inf}"
        )