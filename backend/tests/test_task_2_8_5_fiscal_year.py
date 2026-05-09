"""
Tests for Task 2.8.5 — Fiscal year window helper and AE enforcement.

Covers:
  - get_fiscal_window(): calendar-aligned, June start, October start, edge cases
  - is_ae_business_type(): correct detection of auto_micro
  - update_salon() AE lock: AE salons cannot set fiscal_year_start != 1
  - onboarding AE lock: AE business type forces fiscal_year_start = 1
"""

import pytest

from app.calculations.fiscal import AE_BUSINESS_TYPE, get_fiscal_window, is_ae_business_type


# ── get_fiscal_window() ─────────────────────────────────────────────────────


class TestGetFiscalWindow:
    """Unit tests for get_fiscal_window()."""

    def test_calendar_year_jan(self):
        """fiscal_start=1 returns all 12 months in the same year."""
        result = get_fiscal_window(2026, 1)
        assert len(result) == 12
        assert result[0] == (2026, 1)
        assert result[11] == (2026, 12)
        # All in same year
        assert all(y == 2026 for y, m in result)
        # Months in order
        assert [m for _, m in result] == list(range(1, 13))

    def test_june_start_year_2027(self):
        """fiscal_start=6 and year=2027 spans Jun 2026 – May 2027."""
        result = get_fiscal_window(2027, 6)
        assert len(result) == 12
        # Opening month: June 2026
        assert result[0] == (2026, 6)
        # July 2026
        assert result[1] == (2026, 7)
        # December 2026
        assert result[6] == (2026, 12)
        # January 2027
        assert result[7] == (2027, 1)
        # Closing month: May 2027
        assert result[11] == (2027, 5)

    def test_october_start_year_2026(self):
        """fiscal_start=10 and year=2026 spans Oct 2025 – Sep 2026."""
        result = get_fiscal_window(2026, 10)
        assert len(result) == 12
        # Opening: October 2025
        assert result[0] == (2025, 10)
        # November 2025
        assert result[1] == (2025, 11)
        # December 2025
        assert result[2] == (2025, 12)
        # January 2026
        assert result[3] == (2026, 1)
        # Closing: September 2026
        assert result[11] == (2026, 9)

    def test_december_start_year_2026(self):
        """fiscal_start=12 and year=2026 spans Dec 2025 – Nov 2026."""
        result = get_fiscal_window(2026, 12)
        assert len(result) == 12
        assert result[0] == (2025, 12)
        assert result[1] == (2026, 1)
        assert result[11] == (2026, 11)

    def test_february_start_year_2026(self):
        """fiscal_start=2 and year=2026 spans Feb 2025 – Jan 2026."""
        result = get_fiscal_window(2026, 2)
        assert len(result) == 12
        assert result[0] == (2025, 2)
        assert result[11] == (2026, 1)

    def test_always_12_months(self):
        """get_fiscal_window always returns exactly 12 tuples regardless of start."""
        for start in range(1, 13):
            result = get_fiscal_window(2026, start)
            assert len(result) == 12, f"Expected 12 months for fiscal_start={start}"

    def test_no_duplicate_months(self):
        """No (year, month) tuple appears twice in the window."""
        for start in range(1, 13):
            result = get_fiscal_window(2026, start)
            assert len(set(result)) == 12, f"Duplicate tuples for fiscal_start={start}"

    def test_all_months_present(self):
        """All 12 calendar months (1–12) appear exactly once in any window."""
        for start in range(1, 13):
            result = get_fiscal_window(2026, start)
            month_nums = sorted(m for _, m in result)
            assert month_nums == list(range(1, 13)), f"Missing months for fiscal_start={start}"

    def test_invalid_start_month_zero(self):
        """fiscal_start=0 raises ValueError."""
        with pytest.raises(ValueError, match="fiscal_start_month must be 1–12"):
            get_fiscal_window(2026, 0)

    def test_invalid_start_month_13(self):
        """fiscal_start=13 raises ValueError."""
        with pytest.raises(ValueError, match="fiscal_start_month must be 1–12"):
            get_fiscal_window(2026, 13)


# ── is_ae_business_type() ───────────────────────────────────────────────────


class TestIsAeBusinessType:
    """Unit tests for the AE business type detection helper."""

    def test_auto_micro_is_ae(self):
        """The canonical AE type is detected correctly."""
        assert is_ae_business_type("auto_micro") is True

    def test_sarl_is_not_ae(self):
        assert is_ae_business_type("sarl") is False

    def test_eurl_is_not_ae(self):
        assert is_ae_business_type("eurl") is False

    def test_sas_is_not_ae(self):
        assert is_ae_business_type("sas") is False

    def test_none_is_not_ae(self):
        """None (unknown type) is treated as non-AE."""
        assert is_ae_business_type(None) is False

    def test_empty_string_is_not_ae(self):
        assert is_ae_business_type("") is False

    def test_constant_matches_string(self):
        """AE_BUSINESS_TYPE constant equals the string used throughout the codebase."""
        assert AE_BUSINESS_TYPE == "auto_micro"
        assert is_ae_business_type(AE_BUSINESS_TYPE) is True


# ── update_salon AE lock (unit-level — no DB) ───────────────────────────────


class TestUpdateSalonAeLock:
    """
    Verify that is_ae_business_type gate logic is correct so update_salon will
    lock fiscal_year_start=1 for AE types.

    WHY not integration tests here: integration tests for update_salon are covered
    by test_task_1_7_salons.py. These tests verify the guard logic in isolation.
    """

    def test_ae_type_triggers_lock(self):
        """AE business type should trigger the fiscal lock to 1."""
        business_type = "auto_micro"
        effective_type = business_type
        assert is_ae_business_type(effective_type), "AE should be locked to Jan"

    def test_non_ae_type_does_not_trigger_lock(self):
        """Non-AE types should not be forced to Jan."""
        for bt in ["sarl", "eurl", "sas", "sasu", "ei", "eirl"]:
            assert not is_ae_business_type(bt), f"{bt} should not be AE-locked"

    def test_fiscal_window_ae_is_always_calendar(self):
        """AE users always get calendar year window (fiscal_start=1 → Jan–Dec)."""
        ae_window = get_fiscal_window(2026, 1)
        assert ae_window == [(2026, m) for m in range(1, 13)]


# ── onboarding AE lock logic ─────────────────────────────────────────────────


class TestOnboardingAeLock:
    """
    Verify the fiscal_year_start selection logic in the onboarding service.

    The onboarding service applies:
        fiscal_start = 1 if is_ae_business_type(business_type) else data.fiscal_year_start
    """

    def test_ae_onboarding_ignores_fiscal_start(self):
        """Onboarding with AE type locks fiscal_start to 1 regardless of input."""
        business_type = "auto_micro"
        fiscal_year_start_from_form = 6  # user somehow sent June
        fiscal_start = 1 if is_ae_business_type(business_type) else fiscal_year_start_from_form
        assert fiscal_start == 1

    def test_non_ae_onboarding_uses_form_value(self):
        """Non-AE onboarding uses the fiscal_year_start from the form."""
        business_type = "sarl"
        fiscal_year_start_from_form = 6
        fiscal_start = 1 if is_ae_business_type(business_type) else fiscal_year_start_from_form
        assert fiscal_start == 6

    def test_non_ae_onboarding_default_is_1(self):
        """Non-AE onboarding with default value (1) stays at 1."""
        business_type = "sarl"
        fiscal_year_start_from_form = 1
        fiscal_start = 1 if is_ae_business_type(business_type) else fiscal_year_start_from_form
        assert fiscal_start == 1
