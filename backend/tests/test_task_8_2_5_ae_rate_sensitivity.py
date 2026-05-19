"""
Tests for TASK-8.2.5 — AE rate annual growth sensitivity (AUDIT-8.2.5).

The AE cotisation rate schedule (get_ae_rate) only covers known legislation
up to 2026. Beyond 2026, the engine applies an additive annual increment
controlled by ProjectionInput.ae_rate_annual_growth.

Tests verify:
  - Default (0.000): rates frozen at 2026 level throughout projection.
  - Moderate (0.002): rates grow +0.2pp/year, producing higher charges at year 20.
  - Pessimistic (0.004): rates grow +0.4pp/year.
  - Cap: rates never exceed 50%.
  - AE_RATE_ANNUAL_GROWTH dict has all three scale keys.
"""
from decimal import Decimal

import pytest

from app.calculations.constants import AE_RATE_ANNUAL_GROWTH
from app.calculations.ae_rates import get_ae_rate
from app.calculations.projection import ProjectionInput, project_timeline


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _simple_inp(ae_rate_annual_growth: Decimal = Decimal("0")) -> ProjectionInput:
    """Minimal ProjectionInput for rate sensitivity tests."""
    return ProjectionInput(
        current_age=40,
        target_age=70,
        post_retirement_years=0,  # skip retirement phase
        monthly_gross=Decimal("5000"),
        growth_rate=Decimal("0"),  # flat CA for predictability
        ae_activity_type="bnc_non_reglementee",
        scale="moderate",
        ae_rate_annual_growth=ae_rate_annual_growth,
        current_year=2026,
    )


# ── Constants tests ───────────────────────────────────────────────────────────

def test_ae_rate_annual_growth_has_all_scales():
    """AE_RATE_ANNUAL_GROWTH dict must have all three scale keys."""
    assert "optimistic" in AE_RATE_ANNUAL_GROWTH
    assert "moderate" in AE_RATE_ANNUAL_GROWTH
    assert "pessimistic" in AE_RATE_ANNUAL_GROWTH


def test_optimistic_scale_is_zero():
    """Optimistic scale assumes rates stabilise — growth = 0."""
    assert AE_RATE_ANNUAL_GROWTH["optimistic"] == Decimal("0")


def test_moderate_scale_positive():
    """Moderate scale applies some growth."""
    assert AE_RATE_ANNUAL_GROWTH["moderate"] > Decimal("0")


def test_pessimistic_higher_than_moderate():
    """Pessimistic rate growth must exceed moderate."""
    assert AE_RATE_ANNUAL_GROWTH["pessimistic"] > AE_RATE_ANNUAL_GROWTH["moderate"]


# ── Engine tests ──────────────────────────────────────────────────────────────

def test_zero_growth_frozen_at_2026_rate():
    """With ae_rate_annual_growth=0, ae_rate must stay constant at the 2026 value."""
    inp = _simple_inp(Decimal("0"))
    timeline = project_timeline(inp)

    base_rate = get_ae_rate("bnc_non_reglementee", 2026)
    # All accumulation years should use the frozen 2026 rate
    for year_entry in timeline:
        assert year_entry.ae_rate == base_rate, (
            f"Year {year_entry.year}: expected ae_rate={base_rate}, got {year_entry.ae_rate}"
        )


def test_positive_growth_increases_charges_over_time():
    """With ae_rate_annual_growth=0.002, year 20 charges > year 0 charges (same gross)."""
    inp = _simple_inp(Decimal("0.002"))
    timeline = project_timeline(inp)

    year_0_charges = timeline[0].charges
    year_20_charges = timeline[20].charges  # y=20 → rate +0.4pp over base

    assert year_20_charges > year_0_charges, (
        f"Expected charges to grow with rate: y0={year_0_charges}, y20={year_20_charges}"
    )


def test_rate_growth_mathematically_correct():
    """Verify the exact rate at year 10 matches base_rate + 0.002 × 10."""
    growth = Decimal("0.002")
    inp = _simple_inp(growth)
    timeline = project_timeline(inp)

    base_rate = get_ae_rate("bnc_non_reglementee", 2026)
    expected_rate_y10 = min(Decimal("0.50"), base_rate + growth * 10)
    actual_rate_y10 = timeline[10].ae_rate

    assert actual_rate_y10 == expected_rate_y10, (
        f"Expected ae_rate at y=10: {expected_rate_y10}, got {actual_rate_y10}"
    )


def test_rate_capped_at_50_percent():
    """Extremely high growth rate must be capped at 0.50."""
    # growth=0.05 would take 26% → 156% in 26 years — must cap at 50%
    inp = _simple_inp(Decimal("0.05"))
    timeline = project_timeline(inp)

    for year_entry in timeline:
        assert year_entry.ae_rate <= Decimal("0.50"), (
            f"Year {year_entry.year}: ae_rate={year_entry.ae_rate} exceeds 0.50 cap"
        )


def test_pessimistic_more_charges_than_moderate_at_year_15():
    """Pessimistic scale (0.004/yr) → higher charges at year 15 than moderate (0.002/yr)."""
    pessimistic_growth = AE_RATE_ANNUAL_GROWTH["pessimistic"]
    moderate_growth = AE_RATE_ANNUAL_GROWTH["moderate"]

    inp_pess = _simple_inp(pessimistic_growth)
    inp_mod = _simple_inp(moderate_growth)

    tl_pess = project_timeline(inp_pess)
    tl_mod = project_timeline(inp_mod)

    assert tl_pess[15].charges > tl_mod[15].charges, (
        f"Pessimistic charges ({tl_pess[15].charges}) should exceed moderate ({tl_mod[15].charges})"
    )


def test_year_0_unaffected_by_growth():
    """Year 0 (y=0): ae_rate_annual_growth should NOT be applied (y>0 guard)."""
    inp = _simple_inp(Decimal("0.1"))  # large growth to make any bug obvious
    timeline = project_timeline(inp)

    base_rate = get_ae_rate("bnc_non_reglementee", 2026)
    assert timeline[0].ae_rate == base_rate, (
        f"Year 0 should use frozen base rate, not growth-adjusted rate. "
        f"Expected {base_rate}, got {timeline[0].ae_rate}"
    )
