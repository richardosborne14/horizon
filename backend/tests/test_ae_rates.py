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
        """BNC non-réglementée should return 25.6% for 2026 (decree n°2025-943)."""
        rate = get_ae_rate("bnc_non_reglementee", 2026)
        assert rate == Decimal("0.256")

    def test_known_2025_rate_bnc_non_reglementee(self):
        """BNC non-réglementée should return 24.6% for 2025."""
        rate = get_ae_rate("bnc_non_reglementee", 2025)
        assert rate == Decimal("0.246")

    def test_known_2027_rate_bnc_non_reglementee(self):
        """BNC non-réglementée should return 25.6% for 2027 (stable)."""
        rate = get_ae_rate("bnc_non_reglementee", 2027)
        assert rate == Decimal("0.256")

    def test_known_2024_rate_bnc_non_reglementee(self):
        """BNC non-réglementée: H2 2024 = 23.1%."""
        rate = get_ae_rate("bnc_non_reglementee", 2024, month=7)
        assert rate == Decimal("0.231")

    def test_known_2024_h1_rate_bnc_non_reglementee(self):
        """BNC non-réglementée: H1 2024 = 21.1%."""
        rate = get_ae_rate("bnc_non_reglementee", 2024, month=1)
        assert rate == Decimal("0.211")

    def test_known_2026_rate_bic_services(self):
        """BIC services should return 21.2% (stable since Oct 2022)."""
        rate = get_ae_rate("bic_services", 2026)
        assert rate == Decimal("0.212")

    def test_known_2026_rate_bic_vente(self):
        """BIC vente should return 12.3% (stable since Oct 2022)."""
        rate = get_ae_rate("bic_vente", 2026)
        assert rate == Decimal("0.123")

    def test_known_2026_rate_bnc_cipav(self):
        """BNC CIPAV should return 23.2% for 2026 (stable)."""
        rate = get_ae_rate("bnc_cipav", 2026)
        assert rate == Decimal("0.232")

    def test_rate_for_far_future_uses_latest_projection(self):
        """Far future year returns the latest rate (25.6% for BNC)."""
        rate = get_ae_rate("bnc_non_reglementee", 2050)
        assert rate == Decimal("0.256")

    def test_rate_for_past_year_uses_earliest(self):
        """Year 2005 (before earliest effective entry) returns fallback rate (21.1%)."""
        rate = get_ae_rate("bnc_non_reglementee", 2005)
        assert rate == Decimal("0.211")

    def test_rate_at_entry_boundary_2025(self):
        """Exact from_year starts the new rate (24.6% for 2025)."""
        rate = get_ae_rate("bnc_non_reglementee", 2025)
        assert rate == Decimal("0.246")

    def test_rate_at_entry_boundary_2026(self):
        """Exact from_year starts the new rate (25.6% for 2026)."""
        rate = get_ae_rate("bnc_non_reglementee", 2026)
        assert rate == Decimal("0.256")

    def test_unknown_activity_type_returns_safe_default(self):
        """Invalid activity type should return safe default (25.6%)."""
        rate = get_ae_rate("invalid_type", 2026)
        assert rate == Decimal("0.256")


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
        URSSAF = 60000 * 0.256 = 15360
        CFE = 300
        Total = 15660
        """
        result = compute_annual_charges(
            Decimal("60000"), "bnc_non_reglementee", 2026
        )
        assert result["rate"] == Decimal("0.256")
        assert result["urssaf_and_others"] == Decimal("15360.00")
        assert result["cfe"] == Decimal("300")
        assert result["total"] == Decimal("15660.00")

    def test_known_case_30000_bic_services_2026(self):
        """30 000€ gross BIC services in 2026:
        URSSAF = 30000 * 0.212 = 6360
        CFE = 300
        Total = 6660
        """
        result = compute_annual_charges(
            Decimal("30000"), "bic_services", 2026
        )
        assert result["rate"] == Decimal("0.212")
        assert result["urssaf_and_others"] == Decimal("6360.00")
        assert result["cfe"] == Decimal("300")
        assert result["total"] == Decimal("6660.00")

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

    def test_get_rate_schedule_lists_valid_types(self):
        """Error message should include the list of valid types."""
        with pytest.raises(ValueError) as exc_info:
            get_rate_schedule("bar")
        msg = str(exc_info.value)
        assert "bnc_non_reglementee" in msg
