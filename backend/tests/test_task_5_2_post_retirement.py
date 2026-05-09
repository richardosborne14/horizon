"""
Post-retirement drawdown tests (TASK-5.2).

Tests the full lifecycle: accumulation → retirement → wealth drawdown.
"""
from decimal import Decimal

from app.calculations.projection import (
    ProjectionInput,
    compute_summary,
    find_wealth_exhaustion_age,
    project_timeline,
)


def _approx(expected: Decimal, actual: Decimal, tolerance: Decimal = Decimal("1.00")):
    diff = abs(actual - expected)
    assert diff <= tolerance, f"Expected ~{expected}, got {actual} (diff={diff})"


def test_retirement_phase_produces_extended_timeline():
    """With default 25 post-retirement years, timeline extends past retirement.
    
    Note: wealth may exhaust before the full 25 years pass — that's correct
    behavior. The test verifies we get at least some post-retirement entries.
    """
    inp = ProjectionInput(
        current_age=40, target_age=70, current_year=2026,
        monthly_gross=Decimal("5000"), monthly_expenses_total=Decimal("2000"),
        scale="moderate",
        allocations={
            "livret_a": {"balance": Decimal("500000"), "monthly": Decimal("500")},
            "pea": {"balance": Decimal("200000"), "monthly": Decimal("300")},
        },
    )
    timeline = project_timeline(inp)
    # With substantial savings, post-retirement phase should exist (>30 years)
    assert len(timeline) > 30, f"Expected >30 years, got {len(timeline)}"
    # First year is always accumulation
    assert timeline[0].is_retirement is False
    # There should be retirement entries
    retirement_idx = next(
        i for i, t in enumerate(timeline) if t.is_retirement
    )
    assert retirement_idx == 30  # 30 accumulation years
    assert timeline[-1].is_retirement is True


def test_retirement_work_income_drops_to_zero():
    """After retirement, gross_annual must be zero."""
    inp = ProjectionInput(
        current_age=40, target_age=70, current_year=2026,
        monthly_gross=Decimal("5000"), scale="moderate",
    )
    timeline = project_timeline(inp)
    ret_years = [t for t in timeline if t.is_retirement]
    for t in ret_years:
        assert t.gross_annual in (Decimal("0"), Decimal("0.00"))
        assert t.charges in (Decimal("0"), Decimal("0.00"))
        assert t.cfe in (Decimal("0"), Decimal("0.00"))


def test_retirement_expenses_continue():
    """Expenses should continue (not drop to zero) after retirement."""
    inp = ProjectionInput(
        current_age=40, target_age=70, current_year=2026,
        monthly_gross=Decimal("5000"), monthly_expenses_total=Decimal("3000"),
        scale="moderate",
    )
    timeline = project_timeline(inp)
    ret_years = [t for t in timeline if t.is_retirement]
    for t in ret_years:
        assert t.base_expenses > Decimal("0")


def test_wealth_exhaustion_detected():
    """With low savings and high expenses, wealth should exhaust."""
    inp = ProjectionInput(
        current_age=40, target_age=70, current_year=2026,
        monthly_gross=Decimal("3000"), monthly_expenses_total=Decimal("2500"),
        scale="moderate",
        allocations={
            "livret_a": {"balance": Decimal("20000"), "monthly": Decimal("0")},
        },
    )
    timeline = project_timeline(inp)
    exhaustion_age = find_wealth_exhaustion_age(timeline)
    # With 20k savings and expenses > income, wealth should run out
    assert exhaustion_age is not None
    assert exhaustion_age < 95


def test_wealth_never_exhausts_with_enough_assets():
    """With large pension and savings, wealth may last the full simulation."""
    inp = ProjectionInput(
        current_age=40, target_age=70, current_year=2026,
        monthly_gross=Decimal("8000"), monthly_expenses_total=Decimal("1000"),
        scale="optimistic",
        pension_monthly=Decimal("2000"),  # substantial pension
        allocations={
            "pea": {"balance": Decimal("500000"), "monthly": Decimal("1000")},
            "av_uc": {"balance": Decimal("300000"), "monthly": Decimal("500")},
        },
    )
    timeline = project_timeline(inp)
    # Should never exhaust — wealth at end should be > 0
    assert timeline[-1].total_wealth > Decimal("0")


def test_withdrawal_occurs_when_shortfall():
    """When expenses exceed retirement income, withdrawal should be non-zero."""
    inp = ProjectionInput(
        current_age=40, target_age=70, current_year=2026,
        monthly_gross=Decimal("3000"), monthly_expenses_total=Decimal("2500"),
        scale="moderate",
        allocations={
            "livret_a": {"balance": Decimal("100000"), "monthly": Decimal("0")},
        },
    )
    timeline = project_timeline(inp)
    ret_years = [t for t in timeline if t.is_retirement]
    withdrawals = [t.withdrawal_annual for t in ret_years if t.withdrawal_annual > 0]
    assert len(withdrawals) > 0, "Expected at least some withdrawal years"


def test_summary_includes_retirement_fields():
    """compute_summary should return retirement_monthly_income and gap."""
    inp = ProjectionInput(
        current_age=40, target_age=70, current_year=2026,
        monthly_gross=Decimal("5000"), monthly_expenses_total=Decimal("3000"),
        scale="moderate",
        allocations={
            "livret_a": {"balance": Decimal("50000"), "monthly": Decimal("0")},
        },
    )
    timeline = project_timeline(inp)
    summary = compute_summary(timeline)
    assert "wealth_exhaustion_age" in summary
    assert "retirement_monthly_income" in summary
    assert "retirement_monthly_gap" in summary
    # Gap should be negative (expenses > income at retirement with no pension)
    gap = Decimal(summary["retirement_monthly_gap"])
    assert gap < Decimal("0")


def test_post_retirement_years_configurable():
    """User can set post_retirement_years=0 to skip the retirement phase."""
    inp = ProjectionInput(
        current_age=40, target_age=70, current_year=2026,
        post_retirement_years=0,
        monthly_gross=Decimal("3000"), scale="moderate",
    )
    timeline = project_timeline(inp)
    assert len(timeline) == 30
    assert not any(t.is_retirement for t in timeline)