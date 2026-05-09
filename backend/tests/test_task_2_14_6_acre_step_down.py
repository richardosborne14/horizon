"""
TASK-2.14.6: ACRE step-down tests.

Verifies that acre_rate_for() correctly returns:
  - Decimal("0.50") before 2026-07-01
  - Decimal("0.25") from 2026-07-01 onwards
  - Accepts None (uses today, just checks it returns a valid Decimal)

Source: dev-docs/resources/06-social-charges-reference.md §2 + LFSS 2026 art. 7.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.calculations.social_charges import (
    ACRE_STEP_DOWN_DATE,
    acre_rate_for,
    calc_ae_urssaf_cotisations,
)


class TestAcreStepDownDate:
    """Verify the ACRE_STEP_DOWN_DATE constant is 2026-07-01."""

    def test_step_down_date_is_2026_07_01(self):
        """Constant must match the legislative date in LFSS 2026."""
        assert ACRE_STEP_DOWN_DATE == date(2026, 7, 1)


class TestAcreRateFor:
    """Test the acre_rate_for() helper with explicit dates."""

    def test_pre_step_down_returns_50pct(self):
        """Last day before step-down: 2026-06-30 → 50% exoneration."""
        rate = acre_rate_for(date(2026, 6, 30))
        assert rate == Decimal("0.50"), f"Expected 0.50, got {rate}"

    def test_post_step_down_returns_25pct(self):
        """First day of new regime: 2026-07-01 → 25% exoneration."""
        rate = acre_rate_for(date(2026, 7, 1))
        assert rate == Decimal("0.25"), f"Expected 0.25, got {rate}"

    def test_none_date_returns_valid_decimal(self):
        """Passing None should use date.today() and return a valid Decimal."""
        rate = acre_rate_for(None)
        assert rate in (Decimal("0.50"), Decimal("0.25")), (
            f"Expected 0.50 or 0.25, got {rate}"
        )

    def test_well_before_step_down_returns_50pct(self):
        """A date well before the reform (Jan 2026) returns 50%."""
        rate = acre_rate_for(date(2026, 1, 1))
        assert rate == Decimal("0.50")

    def test_well_after_step_down_returns_25pct(self):
        """A date well after the reform (Dec 2026) returns 25%."""
        rate = acre_rate_for(date(2026, 12, 31))
        assert rate == Decimal("0.25")

    def test_boundary_exact_match_returns_25pct(self):
        """Exactly on the boundary date (2026-07-01) returns 25%."""
        rate = acre_rate_for(ACRE_STEP_DOWN_DATE)
        assert rate == Decimal("0.25")


class TestAcreInCalcAeUrssaf:
    """Integration tests: acre_rate_for result flows correctly into AE calc."""

    def test_acre_pre_step_down_halves_rate(self):
        """
        Before step-down: ACRE halves BIC services rate (21.2% × 50% = 10.6%).
        Cotisations on 4000 € = 4000 × 0.106 = 424.00 €.
        """
        cotisations, rate, _ = calc_ae_urssaf_cotisations(
            Decimal("4000"),
            "bic_services",
            has_acre=True,
            acre_apres_juillet_2026=False,
        )
        assert rate == Decimal("0.1060")
        assert cotisations == Decimal("424.00")

    def test_acre_post_step_down_applies_75pct(self):
        """
        After step-down: ACRE gives only 25% exo → 75% of base rate.
        21.2% × 75% = 0.159. Cotisations on 4000 € = 4000 × 0.159 = 636.00 €.
        """
        cotisations, rate, _ = calc_ae_urssaf_cotisations(
            Decimal("4000"),
            "bic_services",
            has_acre=True,
            acre_apres_juillet_2026=True,
        )
        assert rate == Decimal("0.1590")
        assert cotisations == Decimal("636.00")
