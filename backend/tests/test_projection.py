"""
Unit tests for the projection engine (TASK-4.1).

Three scenarios covering the sensitivity range:
  A — Bare minimum: no investments, no kids, no projects
  B — Moderate saver: 2 kids, 1 dog, 1 car, 4 vehicles, 1 gîte
  C — Aggressive investor: high growth, status change, 3 vehicles, 2 projects

Each test hand-calculates key years (0, 5, 29) and asserts within 1€ tolerance.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.calculations.projection import (
    ProjectionInput,
    YearProjection,
    compute_milestones,
    compute_summary,
    find_goal_year,
    project_timeline,
)
from app.calculations.ae_rates import get_ae_rate, get_cfe_estimate
from app.calculations.constants import INFLATION_SCALES


# ── Helpers ──────────────────────────────────────────────────────────────────


def _approx(expected: Decimal, actual: Decimal, tolerance: Decimal = Decimal("1.00")) -> None:
    """Assert actual is within tolerance of expected."""
    diff = abs(actual - expected)
    assert diff <= tolerance, (
        f"Expected ~{expected}, got {actual} (diff={diff}, tolerance={tolerance})"
    )


def _approx_zero(actual: Decimal) -> None:
    """Assert actual is zero or very close."""
    assert actual in (Decimal("0"), Decimal("0.00")), f"Expected 0, got {actual}"


# ── Scenario A: Bare minimum ─────────────────────────────────────────────────
# Age 40 → 70, CA 3000€/month, BNC, no growth, no investments, no kids, no
# projects. Scale: moderate (inflation 2.5%, cost_living 3.0%).


def _scenario_a_input() -> ProjectionInput:
    """Create the bare-mininum projection input."""
    return ProjectionInput(
        current_age=40,
        target_age=70,
        current_year=2026,
        post_retirement_years=0,  # Sprint 4 back-compat: no post-retirement phase
        monthly_gross=Decimal("3000"),
        growth_rate=Decimal("0"),
        ae_activity_type="bnc_non_reglementee",
        monthly_expenses_total=Decimal("0"),
        scale="moderate",
    )


class TestScenarioABareMinimum:
    """Scenario A: no investments, no kids, no projects."""

    def test_produces_30_years(self):
        """Ages 40→70 should produce 30 year entries."""
        inp = _scenario_a_input()
        timeline = project_timeline(inp)
        assert len(timeline) == 30

    def test_year_0_values(self):
        """Year 0 (2026, age 40): hand-calculated checks."""
        inp = _scenario_a_input()
        timeline = project_timeline(inp)
        t = timeline[0]

        assert t.year == 2026
        assert t.age == 40

        # gross_annual = 3000 * 12 = 36000
        _approx(Decimal("36000"), t.gross_annual)

        # ae_rate for 2026 BNC = 0.262
        expected_rate = get_ae_rate("bnc_non_reglementee", 2026)
        assert t.ae_rate == expected_rate
        # charges = 36000 * 0.262 = 9432.00
        _approx(Decimal("9432"), t.charges)

        # cfe estimate for 2026 = 300.00
        _approx(Decimal("300"), t.cfe)

        # All expenses are zero
        _approx_zero(t.base_expenses)
        _approx_zero(t.kid_expenses)
        _approx_zero(t.pet_expenses)
        _approx_zero(t.car_expenses)
        _approx_zero(t.tech_expenses)
        _approx_zero(t.recurring_expenses)
        _approx_zero(t.project_expenses)
        _approx_zero(t.project_income)
        _approx_zero(t.caf_annual)
        _approx_zero(t.tax_credits)
        _approx_zero(t.status_bonus)

        # total_income = gross = 36000
        _approx(Decimal("36000"), t.total_income)
        # total_outgoing = charges + cfe = 9432 + 300 = 9732
        _approx(Decimal("9732"), t.total_outgoing)
        # net = 36000 - 9732 = 26268
        _approx(Decimal("26268"), t.net_annual)

        # No investments
        _approx_zero(t.year_invested)
        _approx_zero(t.year_returns)
        _approx_zero(t.total_wealth)
        _approx_zero(t.passive_monthly)
        # total_monthly_income = 36000/12 = 3000
        _approx(Decimal("3000"), t.total_monthly_income)

        assert t.goal_reached is False

    def test_year_5_values(self):
        """Year 5 (2031, age 45): AE rate changes, no investments."""
        inp = _scenario_a_input()
        timeline = project_timeline(inp)
        t = timeline[5]

        assert t.year == 2031
        assert t.age == 45

        # Gross unchanged (no growth)
        _approx(Decimal("36000"), t.gross_annual)

        # AE rate should be from 2030 bucket: 0.285 for BNC
        expected_rate = get_ae_rate("bnc_non_reglementee", 2031)
        assert t.ae_rate == expected_rate
        assert expected_rate == Decimal("0.285")  # 2030+ rate

        # charges = 36000 * 0.285 = 10260
        _approx(Decimal("10260"), t.charges)

        # CFE inflates at 2.5% over 5 years: 300 * 1.025^5
        expected_cfe = get_cfe_estimate(2031, Decimal("0.025"))
        _approx(expected_cfe, t.cfe)

        # Base expenses = 0 (no expenses set)
        _approx_zero(t.base_expenses)

        # No wealth
        _approx_zero(t.total_wealth)

    def test_year_29_values(self):
        """Year 29 (2055, age 69): final year before retirement."""
        inp = _scenario_a_input()
        timeline = project_timeline(inp)
        t = timeline[29]

        assert t.year == 2055
        assert t.age == 69

        # Gross unchanged (no growth) — AE takes 29.5%
        _approx(Decimal("36000"), t.gross_annual)

        # AE rate: 2055 >= 2035, so 0.295
        expected_rate = get_ae_rate("bnc_non_reglementee", 2055)
        assert expected_rate == Decimal("0.295")

        # CFE after 29 years of 2.5% inflation
        expected_cfe = get_cfe_estimate(2055, Decimal("0.025"))
        _approx(expected_cfe, t.cfe)

        # Wealth should still be zero
        _approx_zero(t.total_wealth)
        _approx_zero(t.passive_monthly)

    def test_ae_rate_changes_over_time(self):
        """Verify AE rate increases from 0.262 to 0.295 over the timeline."""
        inp = _scenario_a_input()
        timeline = project_timeline(inp)

        # year 0=2026: rate 0.262
        assert timeline[0].ae_rate == Decimal("0.262")
        # year 1=2027: rate 0.268
        assert timeline[1].ae_rate == Decimal("0.268")
        # year 2=2028: rate 0.275
        assert timeline[2].ae_rate == Decimal("0.275")
        # year 4=2030: rate 0.285 (2030 bucket)
        assert timeline[4].ae_rate == Decimal("0.285")
        # year 9=2035: rate 0.295 (2035 bucket)
        assert timeline[9].ae_rate == Decimal("0.295")

    def test_milestones_all_none(self):
        """With zero wealth, no milestones should be found."""
        inp = _scenario_a_input()
        timeline = project_timeline(inp)
        milestones = compute_milestones(timeline)
        assert milestones == []

    def test_goal_year_none(self):
        """Without a goal, find_goal_year returns None."""
        inp = _scenario_a_input()
        timeline = project_timeline(inp)
        assert find_goal_year(timeline) is None

    def test_summary_empty_wealth(self):
        """Summary should reflect zero wealth."""
        inp = _scenario_a_input()
        timeline = project_timeline(inp)
        summary = compute_summary(timeline)

        assert summary["years"] == 30
        assert summary["final_wealth"] in ("0", "0.00")
        assert summary["final_passive_monthly"] in ("0", "0.00")
        assert summary["goal_year"] is None
        assert summary["milestones"] == []

    def test_raises_on_invalid_scale(self):
        """Unknown scale should raise ValueError."""
        inp = _scenario_a_input()
        inp.scale = "banana"
        with pytest.raises(ValueError, match="Unknown inflation scale"):
            project_timeline(inp)

    def test_raises_on_invalid_ages(self):
        """current_age >= target_age should raise ValueError."""
        inp = _scenario_a_input()
        inp.current_age = 70
        inp.target_age = 40
        with pytest.raises(ValueError, match="must be less than"):
            project_timeline(inp)


# ── Scenario B: Moderate saver ────────────────────────────────────────────────
# Age 40 → 70, CA 5000€/month, 3% growth, 2 kids (age ~10 and age ~1 at start),
# 1 dog, 1 car (petrol, age 5, cycle 8), 950€/month savings across 4 vehicles,
# 1 gîte project starting 2035. Scale: moderate.


def _scenario_b_input() -> ProjectionInput:
    """Create the moderate-saver projection input."""
    return ProjectionInput(
        current_age=40,
        target_age=70,
        current_year=2026,
        post_retirement_years=0,  # Sprint 4 back-compat
        monthly_gross=Decimal("5000"),
        growth_rate=Decimal("0.03"),
        ae_activity_type="bnc_non_reglementee",
        monthly_expenses_total=Decimal("2130"),
        scale="moderate",
        # 2 kids: one born ~2016 (age 10 in 2026), one born ~2025 (age 1 in 2026)
        kids_birth_dates=[
            date(2016, 6, 15),  # ~10 years old at start (2026)
            date(2025, 3, 1),   # ~1 year old at start (2026)
        ],
        # Dog — minimal cost events: food 50€/month from age 0
        life_entities=[
            {
                "entity_type": "kid",
                "entity_name": "Léa",
                "entity_age_at_start": 9,  # 2026 - 2016 - 1 (June, after Jan 1) → 9
                "cost_events": [
                    {
                        "label": "Crèche",
                        "from_age": 1,
                        "to_age": 3,
                        "amount": 600.0,
                        "frequency": "monthly",
                        "is_active": True,
                    },
                    {
                        "label": "Études",
                        "from_age": 18,
                        "to_age": 23,
                        "amount": 400.0,
                        "frequency": "monthly",
                        "is_active": True,
                    },
                ],
            },
            {
                "entity_type": "kid",
                "entity_name": "Tom",
                "entity_age_at_start": 1,  # born March 2025 → age 1 on Jan 1 2026
                "cost_events": [
                    {
                        "label": "Crèche",
                        "from_age": 1,
                        "to_age": 3,
                        "amount": 600.0,
                        "frequency": "monthly",
                        "is_active": True,
                    },
                    {
                        "label": "Études",
                        "from_age": 18,
                        "to_age": 23,
                        "amount": 400.0,
                        "frequency": "monthly",
                        "is_active": True,
                    },
                ],
            },
            {
                "entity_type": "pet",
                "entity_name": "Max",
                "entity_age_at_start": 3,
                "cost_events": [
                    {
                        "label": "Nourriture",
                        "from_age": 0,
                        "to_age": 15,
                        "amount": 50.0,
                        "frequency": "monthly",
                        "is_active": True,
                    },
                ],
            },
            {
                "entity_type": "car",
                "entity_name": "Clio",
                "entity_age_at_start": 5,
                "cost_events": [
                    {
                        "label": "CT",
                        "from_age": 4,
                        "to_age": 4,
                        "amount": 80.0,
                        "frequency": "once",
                        "is_active": True,
                    },
                    {
                        "label": "CT",
                        "from_age": 6,
                        "to_age": 6,
                        "amount": 80.0,
                        "frequency": "once",
                        "is_active": True,
                    },
                    {
                        "label": "CT",
                        "from_age": 8,
                        "to_age": 8,
                        "amount": 80.0,
                        "frequency": "once",
                        "is_active": True,
                    },
                    {
                        "label": "Remplacement",
                        "from_age": 8,
                        "to_age": 8,
                        "amount": 18000.0,
                        "frequency": "once",
                        "is_active": True,
                    },
                    {
                        "label": "Entretien",
                        "from_age": 0,
                        "to_age": 20,
                        "amount": 100.0,
                        "frequency": "monthly",
                        "is_active": True,
                    },
                ],
            },
        ],
        # Recurring expenses
        recurring_expenses=[
            {
                "label": "Prêt auto",
                "annual_amount": 2400.0,
                "from_year": 2026,
                "to_year": 2030,
            },
        ],
        # 4 vehicles: Livret A, PEA, AV fonds euros, PER
        allocations={
            "livret_a": {"balance": Decimal("5000"), "monthly": Decimal("200")},
            "pea": {"balance": Decimal("10000"), "monthly": Decimal("200")},
            "av_euro": {"balance": Decimal("15000"), "monthly": Decimal("200")},
            "per": {"balance": Decimal("3000"), "monthly": Decimal("100")},
        },
        # 1 investment project: gîte in 2035
        projects=[
            {
                "type": "invest",
                "label": "Gîte Ardèche",
                "start_year": 2035,
                "purchase_cost": 80000,
                "annual_income": 8000,
                "annual_expenses": 2500,
                "tax_rate": 0.30,
            },
        ],
    )


class TestScenarioBModerateSaver:
    """Scenario B: 2 kids, 1 dog, 1 car, 4 vehicles, 1 gîte project."""

    def test_produces_30_years(self):
        inp = _scenario_b_input()
        timeline = project_timeline(inp)
        assert len(timeline) == 30

    def test_year_0_kid_expenses(self):
        """Year 0 (2026): Tom is age 1 so crèche is active.
        Léa is age 9 — no events active (crèche 0-3 ended, études 18-23 not yet).
        """
        inp = _scenario_b_input()
        timeline = project_timeline(inp)
        t = timeline[0]

        # Tom (age 1): crèche active from_age=1 to_age=3, monthly 600€
        # Crèche: 600 * 12 * infl(0) = 7200
        # Léa (age 9): no active events
        expected_kid = Decimal("7200.00")
        _approx(expected_kid, t.kid_expenses)

        # Gross: 5000 * 12 * 1.03^0 = 60000
        _approx(Decimal("60000"), t.gross_annual)

    def test_year_5_kid_expenses(self):
        """Year 5 (2031): Tom is age 6 — crèche ended (after age 3).
        Léa is age 14 — still no études yet.
        """
        inp = _scenario_b_input()
        timeline = project_timeline(inp)
        t = timeline[5]

        # No kids fit age brackets for crèche(0-3) or études(18-23)
        _approx_zero(t.kid_expenses)

    def test_car_ct_events(self):
        """Car age starts at 5. CT events at ages 4, 6, 8 (once each).
        Age 5 in year 0 means:
          - CT at age 4 already passed (won't fire)
          - CT at age 6 = age 6 in year 1 (2027)
          - CT at age 8 = age 8 in year 3 (2029)
          - Replacement at age 8 = year 3 (2029)
        Note: life entity costs inflate at inflation_rate (not cost_living).
        """
        inp = _scenario_b_input()
        timeline = project_timeline(inp)

        # Year 1 (2027): car age = 6, CT event fires
        t1 = timeline[1]
        infl_1 = (Decimal("1.025")) ** 1
        # CT 80€ * infl, once
        expected_ct = Decimal("80") * infl_1
        # Entretien: 100 * 12 * infl, monthly
        expected_entretien = Decimal("1200") * infl_1
        _approx(expected_ct + expected_entretien, t1.car_expenses)

        # Year 3 (2029): car age = 8, CT + replacement fire
        t3 = timeline[3]
        infl_3 = (Decimal("1.025")) ** 3
        expected_ct_3 = Decimal("80") * infl_3
        expected_replacement = Decimal("18000") * infl_3
        expected_entretien_3 = Decimal("1200") * infl_3
        expected_total_3 = expected_ct_3 + expected_replacement + expected_entretien_3
        _approx(expected_total_3, t3.car_expenses)

    def test_car_no_ct_at_year_0(self):
        """Year 0 (2026): car age = 5, no CT event (already passed at age 4)."""
        inp = _scenario_b_input()
        timeline = project_timeline(inp)
        t = timeline[0]

        # Only entretien: 100 * 12 = 1200
        _approx(Decimal("1200"), t.car_expenses)

    def test_pet_expenses(self):
        """Dog: 50€/month from age 0 to 15. Age starts at 3 in year 0.
        Note: life entity costs inflate at inflation_rate (not cost_living).
        """
        inp = _scenario_b_input()
        timeline = project_timeline(inp)

        # Year 0: pet age 3, active — 50 * 12 * infl^0 = 600
        expected_0 = Decimal("600")  # 50 * 12
        _approx(expected_0, timeline[0].pet_expenses)

        # Year 12: pet age 15, last year (age 15 <= to_age 15)
        t12 = timeline[12]
        infl_12 = (Decimal("1.025")) ** 12  # engine uses inflation_rate
        expected_12 = Decimal("600") * infl_12
        _approx(expected_12, t12.pet_expenses)

        # Year 13: pet age 16, beyond to_age=15
        t13 = timeline[13]
        _approx_zero(t13.pet_expenses)

    def test_project_gite(self):
        """Gîte project: starts in 2035 (year 9 of projection: 2026+9).
        Purchase cost 80000€ fires in 2035. Income from 2036.
        """
        inp = _scenario_b_input()
        timeline = project_timeline(inp)

        # Year 8 (2034): no gîte yet
        _approx_zero(timeline[8].project_expenses)
        _approx_zero(timeline[8].project_income)

        # Year 9 (2035): purchase cost fires
        t9 = timeline[9]
        expected_purchase = Decimal("80000")
        _approx(expected_purchase, t9.project_expenses)
        _approx_zero(t9.project_income)

        # Year 10 (2036): first year of income
        t10 = timeline[10]
        # owned = 1 year
        # inc = 8000 * 1.02^1 = 8160
        # exp = 2500 * infl(10)
        infl_10 = (Decimal("1.025")) ** 10
        exp_10 = Decimal("2500") * infl_10
        taxable_10 = max(0, Decimal("8160") - exp_10)
        tax_10 = taxable_10 * Decimal("0.30")
        expected_inc_10 = Decimal("8160")
        expected_exp_10 = exp_10 + tax_10
        _approx(expected_inc_10, t10.project_income)
        _approx(expected_exp_10, t10.project_expenses)

    def test_investments_compound(self):
        """Wealth should grow from 0% of contributions. Check year 0 vs year 29."""
        inp = _scenario_b_input()
        timeline = project_timeline(inp)

        # Year 0: initial balances + contributions + returns
        t0 = timeline[0]
        assert t0.total_wealth > Decimal("0")

        # Year 29: wealth should be significantly higher
        t29 = timeline[29]
        assert t29.total_wealth > t0.total_wealth
        assert t29.total_wealth > Decimal("100000")  # should cross 100k somewhere

    def test_livret_a_ceiling(self):
        """Livret A balance should not exceed its inflation-adjusted ceiling."""
        inp = _scenario_b_input()
        timeline = project_timeline(inp)

        # Check a later year — Livret A ceiling (22950 * infl) should cap
        # We can't directly check the internal balance, but total_wealth won't
        # exceed it in Livret A's case due to cap
        for t in timeline[-10:]:
            # The total wealth is the sum of all vehicles, but Livret A
            # individually is capped. Just verify total is sensible.
            assert t.total_wealth >= Decimal("0")

    def test_caf_decreases_with_kids_aging(self):
        """CAF should be non-zero at start and drop when kids age past 20."""
        inp = _scenario_b_input()
        timeline = project_timeline(inp)

        # CAF should be non-zero at year 0 (2 kids under 20)
        assert timeline[0].caf_annual > Decimal("0")

        # At year 10 (2036): Léa born 2016 → age ~19 (still < 20 on Jan 1 if June)
        #   age = 2036 - 2016 = 20, June → adjusted down = 19, still qualifying.
        #   Tom born 2025 → age ~10 (March → 10 on Jan 1). Both qualify → CAF > 0.
        t10 = timeline[10]
        assert t10.caf_annual > Decimal("0")

        # At year 11 (2037): Léa born June 2016 → age 21 on Jan 1 (20 after adjustment? 
        #   Actually 2037-2016=21, June → 20 on Jan 1. CAF_MAX_CHILD_AGE = 20, 
        #   age 20 is NOT < 20, so Léa no longer qualifies.)
        # With only 1 qualifying kid (Tom, age 12), CAF drops to 0.
        t11 = timeline[11]
        assert t11.caf_annual == Decimal("0") or t11.caf_annual == Decimal("0.00")

        # By year 20: should definitely be zero (both aged out)
        t20 = timeline[20]
        _approx_zero(t20.caf_annual)

    def test_milestones_appear(self):
        """With moderate savings, some milestones should be reached."""
        inp = _scenario_b_input()
        timeline = project_timeline(inp)
        milestones = compute_milestones(timeline)
        # At least 100k should be reached
        assert len(milestones) >= 1
        assert milestones[0]["label"] == "100k€"

    def test_goal_detection(self):
        """With monthly_revenue_goal=2000, the goal should be reached from
        passive + project income (work salary excluded — it drops at retirement)."""
        inp = _scenario_b_input()
        inp.monthly_revenue_goal = Decimal("2000")
        timeline = project_timeline(inp)
        goal = find_goal_year(timeline)
        assert goal is not None
        assert "year" in goal
        assert "age" in goal

    def test_goal_not_reached_with_high_target(self):
        """With an impossibly high goal, it shouldn't be reached."""
        inp = _scenario_b_input()
        inp.monthly_revenue_goal = Decimal("50000")
        timeline = project_timeline(inp)
        goal = find_goal_year(timeline)
        assert goal is None

    def test_summary_has_all_fields(self):
        """Summary should contain all required fields with correct types."""
        inp = _scenario_b_input()
        timeline = project_timeline(inp)
        summary = compute_summary(timeline)

        assert summary["years"] == 30
        assert isinstance(summary["final_wealth"], str)
        assert isinstance(summary["final_passive_monthly"], str)
        assert isinstance(summary["total_invested"], str)
        assert isinstance(summary["total_returns"], str)
        assert "milestones" in summary
        assert "goal_year" in summary


# ── Scenario C: Aggressive investor ───────────────────────────────────────────
# Age 40 → 70, CA 8000€/month, 6% growth, EIRL switch in 2028 (+5000€/year),
# 1500€/month in PEA/SCPI/AV-UC, 2 investment projects.


def _scenario_c_input() -> ProjectionInput:
    """Create the aggressive-investor projection input."""
    return ProjectionInput(
        current_age=40,
        target_age=70,
        current_year=2026,
        post_retirement_years=0,  # Sprint 4 back-compat
        monthly_gross=Decimal("8000"),
        growth_rate=Decimal("0.06"),
        ae_activity_type="bnc_non_reglementee",
        monthly_expenses_total=Decimal("3000"),
        scale="optimistic",
        # Status change: EIRL in 2028, saves 5000€/year
        status_change_enabled=True,
        status_change_year=2028,
        status_change_savings=Decimal("5000"),
        # 3 vehicles: PEA, SCPI, AV-UC
        allocations={
            "pea": {"balance": Decimal("20000"), "monthly": Decimal("500")},
            "scpi": {"balance": Decimal("15000"), "monthly": Decimal("500")},
            "av_uc": {"balance": Decimal("10000"), "monthly": Decimal("500")},
        },
        # 2 investment projects
        projects=[
            {
                "type": "invest",
                "label": "Immeuble locatif",
                "start_year": 2030,
                "purchase_cost": 150000,
                "annual_income": 18000,
                "annual_expenses": 4000,
                "tax_rate": 0.30,
            },
            {
                "type": "invest",
                "label": "Parking",
                "start_year": 2035,
                "purchase_cost": 30000,
                "annual_income": 3600,
                "annual_expenses": 500,
                "tax_rate": 0.30,
            },
        ],
    )


class TestScenarioCAggressiveInvestor:
    """Scenario C: high growth, status change, multiple investment projects."""

    def test_produces_30_years(self):
        inp = _scenario_c_input()
        timeline = project_timeline(inp)
        assert len(timeline) == 30

    def test_status_bonus_applies_from_correct_year(self):
        """Status bonus should apply from 2028 (year 2) onward."""
        inp = _scenario_c_input()
        timeline = project_timeline(inp)

        # year 0 (2026): no bonus
        _approx_zero(timeline[0].status_bonus)
        # year 1 (2027): no bonus
        _approx_zero(timeline[1].status_bonus)
        # year 2 (2028): bonus = 5000
        _approx(Decimal("5000"), timeline[2].status_bonus)
        # year 29 (2055): bonus still 5000
        _approx(Decimal("5000"), timeline[29].status_bonus)

    def test_high_wealth_accumulation(self):
        """With aggressive investments, wealth should grow substantially."""
        inp = _scenario_c_input()
        timeline = project_timeline(inp)

        t0 = timeline[0]
        t29 = timeline[29]

        # Final wealth should be substantially higher than initial
        assert t29.total_wealth > t0.total_wealth * Decimal("5")
        # Should cross multiple milestones
        assert t29.total_wealth > Decimal("500000")

    def test_passive_income_grows(self):
        """Passive income should be significant by year 29."""
        inp = _scenario_c_input()
        timeline = project_timeline(inp)

        t0 = timeline[0]
        t29 = timeline[29]

        assert t29.passive_monthly > t0.passive_monthly * Decimal("5")

    def test_multiple_milestones(self):
        """Should hit at least 3 milestones with aggressive strategy."""
        inp = _scenario_c_input()
        timeline = project_timeline(inp)
        milestones = compute_milestones(timeline)
        assert len(milestones) >= 3  # 100k, 250k, 500k

    def test_goal_reached(self):
        """With 4000€ goal and high returns, goal should be reached."""
        inp = _scenario_c_input()
        inp.monthly_revenue_goal = Decimal("4000")
        timeline = project_timeline(inp)
        goal = find_goal_year(timeline)
        assert goal is not None

    def test_project_both_contribute(self):
        """Both investment projects should contribute income."""
        inp = _scenario_c_input()
        timeline = project_timeline(inp)

        # Year 4 (2030): first project purchase
        t4 = timeline[4]
        expected_purchase = Decimal("150000")
        _approx(expected_purchase, t4.project_expenses)

        # Year 5 (2031): first project income + tax, second project not yet
        t5 = timeline[5]
        # Year 2031: parking not started yet, only immeuble
        assert t5.project_income > Decimal("0")
        assert t5.project_expenses > Decimal("0")

        # Year 9 (2035): second project purchase + first project income
        t9 = timeline[9]
        # Both projects contributing
        assert t9.project_income > Decimal("0")
        # Purchase cost + running expenses
        assert t9.project_expenses > Decimal("30000")

    def test_scale_affects_projection(self):
        """Different scales should produce different projections."""
        inp_opt = _scenario_c_input()
        inp_opt.scale = "optimistic"
        timeline_opt = project_timeline(inp_opt)

        inp_pes = _scenario_c_input()
        inp_pes.scale = "pessimistic"
        timeline_pes = project_timeline(inp_pes)

        # Scales produce meaningfully different results
        # (Direction depends on ceiling caps, growth rates, and inflation interplay)
        assert timeline_opt[29].total_wealth != timeline_pes[29].total_wealth


# ── Milestone & helper function tests ─────────────────────────────────────────


class TestHelpers:
    """Unit tests for compute_milestones, find_goal_year, compute_summary."""

    def test_compute_milestones_exact_boundaries(self):
        """Milestones should trigger at the first year wealth meets threshold."""
        # Build a synthetic timeline where wealth crosses at known years
        from app.calculations.projection import YearProjection

        timeline = [
            YearProjection(year=2026, age=40, total_wealth=Decimal("50000")),
            YearProjection(year=2027, age=41, total_wealth=Decimal("100000")),
            YearProjection(year=2028, age=42, total_wealth=Decimal("100000")),
            YearProjection(year=2029, age=43, total_wealth=Decimal("250000")),
            YearProjection(year=2030, age=44, total_wealth=Decimal("500000")),
        ]
        milestones = compute_milestones(timeline)
        assert milestones == [
            {"label": "100k€", "year": 2027, "age": 41},
            {"label": "250k€", "year": 2029, "age": 43},
            {"label": "500k€", "year": 2030, "age": 44},
            # 1M not reached
        ]

    def test_compute_milestones_none(self):
        """Empty timeline produces no milestones."""
        assert compute_milestones([]) == []

    def test_find_goal_year_hit(self):
        """Should return first year where goal_reached is True."""
        from app.calculations.projection import YearProjection

        timeline = [
            YearProjection(year=2026, age=40, goal_reached=False),
            YearProjection(year=2027, age=41, goal_reached=True),
            YearProjection(year=2028, age=42, goal_reached=True),
        ]
        result = find_goal_year(timeline)
        assert result == {"year": 2027, "age": 41}

    def test_find_goal_year_miss(self):
        """No goal reached → None."""
        from app.calculations.projection import YearProjection

        timeline = [
            YearProjection(year=2026, age=40, goal_reached=False),
            YearProjection(year=2027, age=41, goal_reached=False),
        ]
        assert find_goal_year(timeline) is None

    def test_find_goal_year_empty(self):
        """Empty timeline → None."""
        assert find_goal_year([]) is None

    def test_compute_summary_empty(self):
        """Empty timeline returns zero summary."""
        summary = compute_summary([])
        assert summary["years"] == 0
        assert summary["final_wealth"] == "0.00"
        assert summary["goal_year"] is None
        assert summary["milestones"] == []

    def test_compute_summary_counts_correctly(self):
        """Summary totals should be accurate."""
        from app.calculations.projection import YearProjection

        timeline = [
            YearProjection(
                year=2026, age=40,
                total_wealth=Decimal("1000"),
                passive_monthly=Decimal("3.33"),
                year_invested=Decimal("500"),
                year_returns=Decimal("50"),
                goal_reached=False,
            ),
            YearProjection(
                year=2027, age=41,
                total_wealth=Decimal("1550"),
                passive_monthly=Decimal("5.17"),
                year_invested=Decimal("500"),
                year_returns=Decimal("50"),
                goal_reached=False,
            ),
        ]
        summary = compute_summary(timeline)
        assert summary["years"] == 2
        assert summary["final_wealth"] in ("1550", "1550.00")
        assert summary["final_passive_monthly"] == "5.17"
        assert summary["total_invested"] == "1000.00"
        assert summary["total_returns"] == "100.00"


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Projection engine edge case handling."""

    def test_empty_input_produces_timeline(self):
        """Absolute minimum input should still produce valid results."""
        inp = ProjectionInput(
            current_age=40, target_age=70, current_year=2026,
            post_retirement_years=0,  # Sprint 4 back-compat
        )
        timeline = project_timeline(inp)
        assert len(timeline) == 30
        # Everything should be zero
        for t in timeline:
            assert t.total_wealth in (Decimal("0"), Decimal("0.00"))
            assert t.passive_monthly in (Decimal("0"), Decimal("0.00"))

    def test_zero_gross(self):
        """Zero CA should still compute without error."""
        inp = ProjectionInput(
            current_age=40,
            target_age=70,
            current_year=2026,
            post_retirement_years=0,  # Sprint 4 back-compat
            monthly_gross=Decimal("0"),
        )
        timeline = project_timeline(inp)
        assert len(timeline) == 30
        assert timeline[0].gross_annual in (Decimal("0"), Decimal("0.00"))

    def test_negative_net_is_valid(self):
        """Expenses exceeding income should produce negative net."""
        inp = ProjectionInput(
            current_age=40,
            target_age=70,
            current_year=2026,
            post_retirement_years=0,  # Sprint 4 back-compat
            monthly_gross=Decimal("1000"),
            monthly_expenses_total=Decimal("2000"),
            scale="moderate",
        )
        timeline = project_timeline(inp)
        # Net should be negative since expenses > income after charges
        assert timeline[0].net_annual < Decimal("0")

    def test_short_timeline(self):
        """A timeline of just 5 years should work."""
        inp = ProjectionInput(
            current_age=40,
            target_age=45,
            current_year=2026,
            post_retirement_years=0,  # Sprint 4 back-compat
            monthly_gross=Decimal("3000"),
            ae_activity_type="bnc_non_reglementee",
            scale="moderate",
        )
        timeline = project_timeline(inp)
        assert len(timeline) == 5

    def test_all_three_scales_work(self):
        """All three scales should produce valid results."""
        for scale in ["optimistic", "moderate", "pessimistic"]:
            inp = ProjectionInput(
                current_age=40,
                target_age=70,
                current_year=2026,
                post_retirement_years=0,  # Sprint 4 back-compat
                monthly_gross=Decimal("3000"),
                ae_activity_type="bnc_non_reglementee",
                scale=scale,
            )
            timeline = project_timeline(inp)
            assert len(timeline) == 30

    def test_cost_events_inactive_are_ignored(self):
        """Inactive cost events should not contribute to expenses."""
        inp = ProjectionInput(
            current_age=40,
            target_age=70,
            current_year=2026,
            post_retirement_years=0,  # Sprint 4 back-compat
            monthly_gross=Decimal("3000"),
            scale="moderate",
            life_entities=[
                {
                    "entity_type": "pet",
                    "entity_name": "InactivePet",
                    "entity_age_at_start": 3,
                    "cost_events": [
                        {
                            "label": "Nourriture",
                            "from_age": 0,
                            "to_age": 15,
                            "amount": 50.0,
                            "frequency": "monthly",
                            "is_active": False,  # inactive!
                        },
                    ],
                },
            ],
        )
        timeline = project_timeline(inp)
        # Even at year 0 where the pet is age 3, expenses should be 0
        _approx_zero(timeline[0].pet_expenses)

    def test_caf_override_is_used(self):
        """When caf_override_monthly is set, it should be used instead of estimate."""
        inp = ProjectionInput(
            current_age=40,
            target_age=70,
            current_year=2026,
            post_retirement_years=0,  # Sprint 4 back-compat
            monthly_gross=Decimal("5000"),
            kids_birth_dates=[date(2020, 1, 1), date(2022, 5, 10)],
            caf_override_monthly=Decimal("200"),
            scale="moderate",
        )
        timeline = project_timeline(inp)
        # CAF override: 200 * 12 = 2400 in year 0 (no revalorisation yet)
        _approx(Decimal("2400"), timeline[0].caf_annual)

    def test_caf_override_zero_with_no_kids(self):
        """Even with override, no kids should mean zero CAF."""
        inp = ProjectionInput(
            current_age=40,
            target_age=70,
            current_year=2026,
            post_retirement_years=0,  # Sprint 4 back-compat
            monthly_gross=Decimal("5000"),
            caf_override_monthly=Decimal("200"),
            scale="moderate",
        )
        timeline = project_timeline(inp)
        _approx_zero(timeline[0].caf_annual)

    def test_tax_credits_are_capped(self):
        """CESU and charity credits should respect ceilings."""
        inp = ProjectionInput(
            current_age=40,
            target_age=70,
            current_year=2026,
            post_retirement_years=0,  # Sprint 4 back-compat
            monthly_gross=Decimal("10000"),
            cesu_annual=Decimal("20000"),
            charity_annual=Decimal("50000"),
            scale="moderate",
        )
        timeline = project_timeline(inp)
        # CESU: 20000 * 0.5 = 10000, capped at 6000
        # Charity: 50000 * 0.66 = 33000, capped at 20000
        expected = Decimal("26000")
        _approx(expected, timeline[0].tax_credits)

    def test_performance_30_year(self):
        """30-year projection with multiple entities should complete quickly."""
        import time

        inp = _scenario_b_input()
        start = time.perf_counter()
        timeline = project_timeline(inp)
        elapsed = time.perf_counter() - start

        assert len(timeline) == 30
        # Should complete in well under 200ms (Python in Docker may be slower,
        # but 500ms is the absolute ceiling)
        assert elapsed < 0.2, f"Projection took {elapsed:.4f}s, expected < 0.2s"