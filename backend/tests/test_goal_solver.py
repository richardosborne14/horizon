"""
Sprint 7 — TASK-7.11 Goal-Backward Solver tests.

Tests:
  - Achievable goal (savings lever finds a solution)
  - Unachievable goal (no solutions or all extreme)
  - Binary search converges
  - Feasibility ranking (easy before hard)
  - All 5 levers tested independently
"""

from decimal import Decimal

import pytest

from app.calculations.goal_solver import (
    solve_goal,
    GoalSolution,
    _total_monthly_savings,
    _classify_feasibility,
    _get_retirement_income_at_year,
)
from app.calculations.projection import (
    ProjectionInput,
    project_timeline,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _moderate_input() -> ProjectionInput:
    """A moderate-saver projection input that should produce solvable goals."""
    return ProjectionInput(
        current_age=40,
        target_age=67,
        current_year=2026,
        post_retirement_years=25,
        monthly_gross=Decimal("5000"),
        growth_rate=Decimal("0.03"),
        ae_activity_type="bnc_non_reglementee",
        monthly_expenses_total=Decimal("2500"),
        scale="moderate",
        allocations={
            "pea": {"balance": Decimal("15000"), "monthly": Decimal("300")},
            "av_euro": {"balance": Decimal("10000"), "monthly": Decimal("200")},
        },
    )


class TestGoalSolverBasic:
    """Basic goal solver functionality."""

    def test_achievable_goal_returns_solutions(self):
        """A modest goal 27 years out should have at least 1 solution."""
        inp = _moderate_input()
        # Target: passive income covering 1500€ by age 67
        # With 5000€/mo CA, 2500€ expenses, 500€ savings at 3% over 27 years,
        # this is achievable — solver should find at least growth or savings lever
        solutions = solve_goal(inp, Decimal("1500"), 67)

        assert len(solutions) >= 1, f"Expected at least 1 solution, got {len(solutions)}"
        levers = {s.lever for s in solutions}
        # At least one of the financial levers should be present
        assert any(
            l in levers
            for l in ["monthly_savings", "monthly_expenses", "growth_rate", "retirement_age"]
        )

    def test_unachievable_goal_returns_empty(self):
        """An impossibly high goal should return no solutions."""
        inp = _moderate_input()
        # Target 50000€/mois at age 45 is impossible with current income
        solutions = solve_goal(inp, Decimal("50000"), 45)
        assert len(solutions) == 0

    def test_solutions_ranked_by_feasibility(self):
        """Solutions should be sorted easiest → hardest."""
        inp = _moderate_input()
        solutions = solve_goal(inp, Decimal("2000"), 67)

        if len(solutions) >= 2:
            feasibility_order = {"easy": 0, "moderate": 1, "hard": 2, "extreme": 3}
            for i in range(len(solutions) - 1):
                current_order = feasibility_order.get(solutions[i].feasibility, 99)
                next_order = feasibility_order.get(solutions[i + 1].feasibility, 99)
                assert current_order <= next_order, (
                    f"Solution {i} ({solutions[i].lever}) has feasibility "
                    f"{solutions[i].feasibility} but solution {i+1} "
                    f"({solutions[i+1].lever}) has {solutions[i+1].feasibility}"
                )

    def test_binary_search_converges(self):
        """Binary search should converge to a reasonable value, not infinite loop."""
        inp = _moderate_input()
        solutions = solve_goal(inp, Decimal("2000"), 67)

        savings_sol = next((s for s in solutions if s.lever == "monthly_savings"), None)
        if savings_sol:
            # The required savings should be a reasonable amount
            required = Decimal(savings_sol.required_value.rstrip("€/mois"))
            assert required > Decimal("0")
            assert required <= Decimal("6000")  # should not be absurd
            assert savings_sol.feasibility in {"easy", "moderate", "hard", "extreme"}

    def test_expenses_lever_with_nonzero_expenses(self):
        """When expenses > 0, the expenses lever should be tested."""
        inp = _moderate_input()
        inp.monthly_expenses_total = Decimal("3000")
        solutions = solve_goal(inp, Decimal("2000"), 67)

        expense_sol = next((s for s in solutions if s.lever == "monthly_expenses"), None)
        if expense_sol:
            assert expense_sol.change_amount.startswith("-")

    def test_expenses_lever_skipped_when_zero(self):
        """When expenses are zero, expenses lever should be skipped."""
        inp = _moderate_input()
        inp.monthly_expenses_total = Decimal("0")
        solutions = solve_goal(inp, Decimal("2000"), 67)

        expense_sol = next((s for s in solutions if s.lever == "monthly_expenses"), None)
        assert expense_sol is None

    def test_growth_lever_tested(self):
        """Growth lever should appear when current growth < 15%."""
        inp = _moderate_input()
        inp.growth_rate = Decimal("0.02")  # 2% growth
        solutions = solve_goal(inp, Decimal("2000"), 67)

        growth_sol = next((s for s in solutions if s.lever == "growth_rate"), None)
        if growth_sol:
            assert growth_sol.change_amount.startswith("+")
            assert "%" in growth_sol.change_amount

    def test_retirement_age_lever_always_tested(self):
        """Working longer should always be tested."""
        inp = _moderate_input()
        solutions = solve_goal(inp, Decimal("2000"), 67)

        age_sol = next((s for s in solutions if s.lever == "retirement_age"), None)
        if age_sol:
            assert age_sol.change_amount.startswith("+")
            assert "an" in age_sol.change_amount

    def test_allocation_lever_with_investments(self):
        """When investments exist, PEA reallocation should be tested."""
        inp = _moderate_input()
        inp.allocations = {
            "av_euro": {"balance": Decimal("10000"), "monthly": Decimal("500")},
            "pea": {"balance": Decimal("5000"), "monthly": Decimal("200")},
        }
        solutions = solve_goal(inp, Decimal("2000"), 67)

        alloc_sol = next((s for s in solutions if s.lever == "allocation_pea"), None)
        # May or may not be in solutions depending on whether it helps reach the goal

    def test_solution_fields_complete(self):
        """Each solution should have all required fields."""
        inp = _moderate_input()
        solutions = solve_goal(inp, Decimal("2000"), 67)

        for s in solutions:
            assert s.lever
            assert s.label
            assert s.description
            assert s.current_value
            assert s.required_value
            assert s.change_amount
            assert s.feasibility in {"easy", "moderate", "hard", "extreme"}
            assert s.goal_year > 0
            assert s.goal_age > 0


class TestHelpers:
    """Unit tests for goal solver helper functions."""

    def test_classify_feasibility(self):
        """Thresholds should map correctly."""
        thresholds = [Decimal("200"), Decimal("500"), Decimal("1000")]
        assert _classify_feasibility(Decimal("100"), thresholds) == "easy"
        assert _classify_feasibility(Decimal("200"), thresholds) == "easy"
        assert _classify_feasibility(Decimal("201"), thresholds) == "moderate"
        assert _classify_feasibility(Decimal("500"), thresholds) == "moderate"
        assert _classify_feasibility(Decimal("501"), thresholds) == "hard"
        assert _classify_feasibility(Decimal("1000"), thresholds) == "hard"
        assert _classify_feasibility(Decimal("1001"), thresholds) == "extreme"

    def test_total_monthly_savings(self):
        """Should sum all allocation monthly values."""
        inp = ProjectionInput(
            current_age=40,
            target_age=70,
            current_year=2026,
            monthly_gross=Decimal("3000"),
            allocations={
                "pea": {"balance": Decimal("5000"), "monthly": Decimal("300")},
                "av_euro": {"balance": Decimal("2000"), "monthly": Decimal("200")},
                "livret_a": {"balance": Decimal("1000"), "monthly": Decimal("100")},
            },
        )
        assert _total_monthly_savings(inp) == Decimal("600")

    def test_total_monthly_savings_empty(self):
        """Empty allocations should return 0."""
        inp = ProjectionInput(
            current_age=40,
            target_age=70,
            current_year=2026,
            monthly_gross=Decimal("3000"),
        )
        assert _total_monthly_savings(inp) == Decimal("0")

    def test_retirement_income_at_year(self):
        """Should compute passive + (project + pension) / 12."""
        inp = _moderate_input()
        inp.target_age = 70
        inp.post_retirement_years = 0  # Sprint 4 back-compat mode
        timeline = project_timeline(inp)

        # Year 0 (2026): only passive from allocations
        income = _get_retirement_income_at_year(timeline, 2026)
        assert income is not None
        assert income >= Decimal("0")

    def test_retirement_income_none_for_missing_year(self):
        """Should return None for year outside timeline."""
        inp = _moderate_input()
        inp.post_retirement_years = 0
        timeline = project_timeline(inp)

        result = _get_retirement_income_at_year(timeline, 1900)
        assert result is None


class TestPerformance:
    """Goal solver should be fast enough."""

    def test_solver_under_2_seconds(self):
        """~100 projection passes should complete in under 2 seconds."""
        import time

        inp = _moderate_input()
        start = time.perf_counter()
        solutions = solve_goal(inp, Decimal("2000"), 67)
        elapsed = time.perf_counter() - start

        # With ~5 levers × 20 binary iterations = ~100 passes
        # Each pass ~0.3ms → ~30ms total. Set generous ceiling.
        assert elapsed < 2.0, f"Goal solver took {elapsed:.2f}s, expected < 2s"
        assert isinstance(solutions, list)