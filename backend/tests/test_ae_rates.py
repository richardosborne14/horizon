"""
Unit tests for the AE cotisation rate engine (TASK 1.2).

Tests cover:
- Known 2026 rates for all 4 activity types
- Rate lookup for past year (returns earliest applicable)
- Rate lookup for far future year (returns latest applicable)
- Rate lookup for transition year (new rate takes effect)
- compute_annual_charges for a known gross amount
- CFE estimates
- Error handling for unknown activity types
"""

from decimal import Decimal

import pytest

from app.calculations.ae_rates import (
    get_ae_rate,
    get_rate_schedule,
    get_all_schedules,
    get_cfe_estimate,
    compute_annual_charges,
    AE_RATE_SCHEDULE,
)


class TestGetAeRate:
    """Tests for get_ae_rate() — the core rate lookup function."""

    def test_known_2026_rate_bnc_non_reglementee(self):
        """BNC non-réglementée should return 26.2% for 2026."""
        rate = get_ae_rate("bnc_non_reglementee", 2026)
        assert rate == Decimal("0.262")

    def test_known_2026_rate_bic_services(self):
        """BIC services should return 23.7% for 2026."""
        rate = get_ae_rate("bic_services", 2026)
        assert rate == Decimal("0.237")

    def test_known_2026_rate_bic_vente(self):
        """BIC vente should return 14.8% for 2026."""
        rate = get_ae_rate("bic_vente", 2026)
        assert rate == Decimal("0.148")

    def test_known_2026_rate_bnc_cipav(self):
        """BNC CIPAV should return 25.4% for 2026."""
        rate = get_ae_rate("bnc_cipav", 2026)
        assert rate == Decimal("0.254")

    def test_rate_for_year_between_entries(self):
        """Year between two entries should use the earlier entry's rate.

        2029 is between the 2028 entry (0.275) and the 2030 entry (0.285).
        Should return 0.275 (the 2028 entry applies until 2030).
        """
        rate = get_ae_rate("bnc_non_reglementee", 2029)
        assert rate == Decimal("0.275")

    def test_rate_for_far_future_uses_latest_projection(self):
        """Year 2050 should use the latest projected rate (0.295 for BNC)."""
        rate = get_ae_rate("bnc_non_reglementee", 2050)
        assert rate == Decimal("0.295")

    def test_rate_for_past_year_uses_earliest(self):
        """Year 2020 (before earliest 2024 entry) returns earliest rate."""
        rate = get_ae_rate("bnc_non_reglementee", 2020)
        assert rate == Decimal("0.245")

    def test_rate_at_entry_boundary(self):
        """Exact from_year uses that entry's rate."""
        rate = get_ae_rate("bnc_non_reglementee", 2025)
        assert rate == Decimal("0.252")

    def test_rate_at_entry_boundary_2028(self):
        """Exact from_year for 2028 transition."""
        rate = get_ae_rate("bnc_non_reglementee", 2028)
        assert rate == Decimal("0.275")

    def test_unknown_activity_type_raises_valueerror(self):
        """Invalid activity type should raise ValueError with helpful message."""
        with pytest.raises(ValueError) as exc_info:
            get_ae_rate("invalid_type", 2026)
        assert "Unknown activity type" in str(exc_info.value)
        assert "invalid_type" in str(exc_info.value)


class TestGetRateSchedule:
    """Tests for get_rate_schedule() — frontend display data."""

    def test_returns_list_of_dicts(self):
        """Should return a list of dicts with from_year and rate."""
        schedule = get_rate_schedule("bic_vente")
        assert isinstance(schedule, list)
        assert len(schedule) >= 1
        for entry in schedule:
            assert "from_year" in entry
            assert "rate" in entry
            assert isinstance(entry["rate"], str)

    def test_schedule_entries_are_chronological(self):
        """Schedule should be in ascending from_year order."""
        schedule = get_rate_schedule("bnc_non_reglementee")
        years = [entry["from_year"] for entry in schedule]
        assert years == sorted(years)

    def test_unknown_type_raises_valueerror(self):
        """Invalid type should raise ValueError."""
        with pytest.raises(ValueError):
            get_rate_schedule("nope")


class TestGetAllSchedules:
    """Tests for get_all_schedules()."""

    def test_returns_all_four_types(self):
        """Should return schedules for all 4 activity types."""
        all_sched = get_all_schedules()
        assert set(all_sched.keys()) == set(AE_RATE_SCHEDULE.keys())
        for atype in AE_RATE_SCHEDULE:
            assert isinstance(all_sched[atype], list)
            assert len(all_sched[atype]) > 0


class TestGetCfeEstimate:
    """Tests for get_cfe_estimate()."""

    def test_base_year_2026(self):
        """CFE for 2026 should be 300€."""
        cfe = get_cfe_estimate(2026)
        assert cfe == Decimal("300")

    def test_one_year_later_with_default_inflation(self):
        """2027 CFE = 300 * 1.025 = 307.50."""
        cfe = get_cfe_estimate(2027)
        assert cfe == Decimal("307.50")

    def test_one_year_earlier_with_default_inflation(self):
        """2025 CFE = 300 / 1.025 ≈ 292.68 (rounded)."""
        cfe = get_cfe_estimate(2025)
        # 300 / 1.025 = 292.6829... — Decimal handles this precisely
        expected = Decimal("300") / Decimal("1.025")
        assert cfe == expected

    def test_custom_inflation_rate(self):
        """Custom inflation rate of 3%."""
        cfe = get_cfe_estimate(2028, inflation_rate=Decimal("0.03"))
        # 300 * 1.03^2 = 300 * 1.0609 = 318.27
        expected = Decimal("300") * (Decimal("1.03") ** 2)
        assert cfe == expected


class TestComputeAnnualCharges:
    """Tests for compute_annual_charges()."""

    def test_known_case_60000_bnc_2026(self):
        """60 000€ gross BNC in 2026:
        URSSAF = 60000 * 0.262 = 15720
        CFE = 300
        Total = 16020
        """
        result = compute_annual_charges(
            Decimal("60000"), "bnc_non_reglementee", 2026
        )
        assert result["rate"] == Decimal("0.262")
        assert result["urssaf_and_others"] == Decimal("15720.00")
        assert result["cfe"] == Decimal("300")
        assert result["total"] == Decimal("16020.00")

    def test_known_case_30000_bic_services_2026(self):
        """30 000€ gross BIC services in 2026:
        URSSAF = 30000 * 0.237 = 7110
        CFE = 300
        Total = 7410
        """
        result = compute_annual_charges(
            Decimal("30000"), "bic_services", 2026
        )
        assert result["rate"] == Decimal("0.237")
        assert result["urssaf_and_others"] == Decimal("7110.00")
        assert result["cfe"] == Decimal("300")
        assert result["total"] == Decimal("7410.00")

    def test_all_values_are_decimal(self):
        """Every value in the result should be a Decimal."""
        result = compute_annual_charges(
            Decimal("10000"), "bnc_non_reglementee", 2026
        )
        for key, value in result.items():
            assert isinstance(value, Decimal), (
                f"Key '{key}' is {type(value).__name__}, expected Decimal"
            )

    def test_zero_gross_annual(self):
        """Zero gross should produce zero URSSAF but still have CFE."""
        result = compute_annual_charges(
            Decimal("0"), "bnc_non_reglementee", 2026
        )
        assert result["urssaf_and_others"] == Decimal("0")
        assert result["cfe"] == Decimal("300")
        assert result["total"] == Decimal("300")


class TestValueErrorMessages:
    """Ensure error messages are helpful for debugging."""

    def test_get_ae_rate_lists_valid_types(self):
        """Error message should include the list of valid types."""
        with pytest.raises(ValueError) as exc_info:
            get_ae_rate("foo", 2026)
        msg = str(exc_info.value)
        assert "bnc_non_reglementee" in msg
        assert "bic_services" in msg
        assert "bic_vente" in msg
        assert "bnc_cipav" in msg

    def test_get_rate_schedule_lists_valid_types(self):
        """Error message should include the list of valid types."""
        with pytest.raises(ValueError) as exc_info:
            get_rate_schedule("bar")
        msg = str(exc_info.value)
        assert "bnc_non_reglementee" in msg