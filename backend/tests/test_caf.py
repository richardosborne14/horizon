"""
Task 2.4: CAF Auto-Estimation tests.

Tests cover:
- 2 kids under 20, income < 70k → full rate
- 2 kids, income > 93k → quarter rate
- 3 kids → higher base rate
- Kid turns 20 → qualifying count drops
- 0 or 1 kid → returns 0
- Timeline shows CAF dropping
- Income thresholds adjust for additional children
- Revalorisation at 1.5%/year

Run: docker compose exec backend pytest tests/test_caf.py -v
"""

from datetime import date
from decimal import Decimal

from app.calculations.caf import (
    estimate_monthly_caf,
    get_caf_timeline,
    CAF_2026_BASE,
    CAF_PER_ADDITIONAL_CHILD,
)


class TestCAFEstimation:
    """Core CAF estimation logic."""

    def test_two_kids_low_income_full_rate(self):
        """2 kids aged 5 and 8, income 50k → full rate ~148€/month."""
        amount = estimate_monthly_caf(
            kids_birth_dates=[
                date(2021, 3, 15),  # age 5 in 2026
                date(2018, 7, 22),  # age 8 in 2026
            ],
            reference_year=2026,
            annual_household_income=Decimal("50000"),
        )
        assert amount == Decimal("148.00"), (
            f"2 kids, 50k income: expected 148.00, got {amount}"
        )

    def test_two_kids_high_income_quarter_rate(self):
        """2 kids, income > 93k → quarter rate."""
        amount = estimate_monthly_caf(
            kids_birth_dates=[
                date(2021, 3, 15),
                date(2018, 7, 22),
            ],
            reference_year=2026,
            annual_household_income=Decimal("100000"),
        )
        assert amount == Decimal("37.00"), (  # 148 / 4
            f"2 kids, 100k income: expected 37.00, got {amount}"
        )

    def test_two_kids_medium_income_half_rate(self):
        """2 kids, income between 70k and 93k → half rate."""
        amount = estimate_monthly_caf(
            kids_birth_dates=[
                date(2021, 3, 15),
                date(2018, 7, 22),
            ],
            reference_year=2026,
            annual_household_income=Decimal("80000"),
        )
        assert amount == Decimal("74.00"), (  # 148 / 2
            f"2 kids, 80k income: expected 74.00, got {amount}"
        )

    def test_three_kids_higher_rate(self):
        """3 kids → 338€/month."""
        amount = estimate_monthly_caf(
            kids_birth_dates=[
                date(2021, 3, 15),
                date(2018, 7, 22),
                date(2015, 1, 10),
            ],
            reference_year=2026,
            annual_household_income=Decimal("50000"),
        )
        assert amount == Decimal("338.00"), (
            f"3 kids, 50k income: expected 338.00, got {amount}"
        )

    def test_four_kids_rate(self):
        """4 kids → 338 + 190 = 528€/month."""
        amount = estimate_monthly_caf(
            kids_birth_dates=[
                date(2023, 3, 15),
                date(2021, 7, 22),
                date(2019, 1, 10),
                date(2017, 6, 5),
            ],
            reference_year=2026,
            annual_household_income=Decimal("50000"),
        )
        expected = CAF_2026_BASE[3] + CAF_PER_ADDITIONAL_CHILD
        assert amount == expected, (
            f"4 kids, 50k income: expected {expected}, got {amount}"
        )

    def test_one_kid_returns_zero(self):
        """1 kid → 0€ CAF."""
        amount = estimate_monthly_caf(
            kids_birth_dates=[date(2021, 3, 15)],
            reference_year=2026,
            annual_household_income=Decimal("50000"),
        )
        assert amount == Decimal("0")

    def test_zero_kids_returns_zero(self):
        """0 kids → 0€ CAF."""
        amount = estimate_monthly_caf(
            kids_birth_dates=[],
            reference_year=2026,
            annual_household_income=Decimal("50000"),
        )
        assert amount == Decimal("0")

    def test_kid_turns_20_qualifying_drops(self):
        """Kid born 2006-05-15 → age 20 on Jan 1 2027? No, 20 on May 15 2026."""
        # On Jan 1 2026: age 19 → qualifies
        # On Jan 1 2027: age 20 → does NOT qualify
        amount_2026 = estimate_monthly_caf(
            kids_birth_dates=[
                date(2006, 5, 15),
                date(2010, 3, 1),
            ],
            reference_year=2026,
            annual_household_income=Decimal("50000"),
        )
        # Both qualify in 2026 → 148€
        assert amount_2026 == Decimal("148.00"), (
            f"2026: both qualify, expected 148.00, got {amount_2026}"
        )

        amount_2027 = estimate_monthly_caf(
            kids_birth_dates=[
                date(2006, 5, 15),
                date(2010, 3, 1),
            ],
            reference_year=2027,
            annual_household_income=Decimal("50000"),
        )
        # Only 1 qualifies in 2027 → 0€
        assert amount_2027 == Decimal("0"), (
            f"2027: only 1 qualifies, expected 0, got {amount_2027}"
        )

    def test_income_threshold_adjusts_for_more_kids(self):
        """Income thresholds increase by 5k per additional child beyond 2."""
        # 3 kids, income 78k: threshold is 70k + 5k = 75k for full
        # 78k > 75k but < 93k + 5k = 98k → half rate
        amount = estimate_monthly_caf(
            kids_birth_dates=[
                date(2021, 3, 15),
                date(2018, 7, 22),
                date(2015, 1, 10),
            ],
            reference_year=2026,
            annual_household_income=Decimal("78000"),
        )
        # 3 kids full = 338, half = 169
        assert amount == Decimal("169.00"), (
            f"3 kids, 78k income: expected 169.00 (half rate), got {amount}"
        )


class TestCAFTimeline:
    """CAF timeline generation."""

    def test_timeline_shows_drop_when_kid_ages_out(self):
        """Timeline should show CAF dropping from 148 to 0 when oldest turns 20."""
        timeline = get_caf_timeline(
            kids_birth_dates=[
                date(2006, 5, 15),  # turns 20 in 2026, loses qualification in 2027
                date(2010, 3, 1),   # 16 in 2026
            ],
            from_year=2026,
            to_year=2028,
            annual_income=Decimal("50000"),
        )

        # 2026: both qualify → 148€
        assert timeline[0]["year"] == 2026
        assert timeline[0]["qualifying_kids"] == 2
        assert timeline[0]["monthly_amount"] == "148.00"

        # 2027: only 1 qualifies → 0€
        assert timeline[1]["year"] == 2027
        assert timeline[1]["qualifying_kids"] == 1
        assert timeline[1]["monthly_amount"] == "0"

        # 2028: only 1 qualifies → still 0€
        assert timeline[2]["year"] == 2028
        assert timeline[2]["qualifying_kids"] == 1
        assert timeline[2]["monthly_amount"] == "0"

    def test_timeline_revalorises_rates(self):
        """CAF amounts should increase 1.5%/year due to revalorisation."""
        timeline = get_caf_timeline(
            kids_birth_dates=[
                date(2020, 1, 1),
                date(2018, 1, 1),
            ],
            from_year=2026,
            to_year=2028,
            annual_income=Decimal("50000"),
        )

        # 2026: 148.00
        assert timeline[0]["monthly_amount"] == "148.00"

        # 2027: 148 * 1.015 = 150.22
        assert timeline[1]["monthly_amount"] == "150.22"

        # 2028: 148 * 1.015^2 = 152.47
        assert timeline[2]["monthly_amount"] == "152.47"