"""
Goal-backward solver — finds input changes to hit a target at a target age.

Sprint 7 (TASK-7.11): The advisory engine's core tool. Given a target monthly
income and target age, tests each lever independently via binary search to find
the minimum change needed. Returns solutions ranked by feasibility (easy → extreme).

Strategy: binary search on each lever independently, then combine.
For each lever, find the minimum change that makes the goal achievable at
the target age. Then present the options ranked by feasibility.

Performance: ~5 × 15-20 projection passes per request. Target < 3s.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.calculations.projection import (
    ProjectionInput,
    project_timeline,
)


# ── Data structures ────────────────────────────────────────────────────────────


@dataclass
class GoalSolution:
    """One way to reach the goal."""

    lever: str
    label: str
    description: str
    current_value: str
    required_value: str
    change_amount: str
    feasibility: str  # "easy", "moderate", "hard", "extreme"
    goal_year: int
    goal_age: int


# ── Public API ─────────────────────────────────────────────────────────────────


def solve_goal(
    inp: ProjectionInput,
    target_monthly: Decimal,
    target_age: int,
    scale: str = "moderate",
) -> list[GoalSolution]:
    """Find what changes are needed to reach target_monthly by target_age.

    Tests each lever independently via binary search.
    Returns solutions ranked by feasibility (easiest first).

    Args:
        inp: The base ProjectionInput (unchanged).
        target_monthly: Target monthly income at retirement.
        target_age: Target age to reach the goal.
        scale: Inflation scale (passed through to projection).

    Returns:
        List of GoalSolution objects, ranked easiest → hardest.
    """
    solutions: list[GoalSolution] = []

    # Compute target_year from target_age
    birth_year = inp.current_year - inp.current_age
    target_year = birth_year + target_age

    # Lever 1: Increase monthly savings
    savings_solution = _solve_savings(inp, target_monthly, target_year, target_age)
    if savings_solution:
        solutions.append(savings_solution)

    # Lever 2: Reduce monthly expenses
    expense_solution = _solve_expenses(inp, target_monthly, target_year, target_age)
    if expense_solution:
        solutions.append(expense_solution)

    # Lever 3: Increase CA growth rate
    growth_solution = _solve_growth(inp, target_monthly, target_year, target_age)
    if growth_solution:
        solutions.append(growth_solution)

    # Lever 4: Work longer (increase target age)
    age_solution = _solve_retirement_age(inp, target_monthly)
    if age_solution:
        solutions.append(age_solution)

    # Lever 5: Redirect savings to higher-yield vehicle (PEA)
    allocation_solution = _solve_allocation(inp, target_monthly, target_year, target_age)
    if allocation_solution:
        solutions.append(allocation_solution)

    # Rank by feasibility
    feasibility_order = {"easy": 0, "moderate": 1, "hard": 2, "extreme": 3}
    solutions.sort(key=lambda s: feasibility_order.get(s.feasibility, 99))

    return solutions


# ── Lever solvers ──────────────────────────────────────────────────────────────


def _solve_savings(
    inp: ProjectionInput,
    target: Decimal,
    target_year: int,
    target_age: int,
) -> GoalSolution | None:
    """Binary search: how much more monthly savings to hit the goal?

    Tests additional monthly savings from 0€ to 5,000€.
    Adds to the best available investment vehicle.
    """
    current_savings = _total_monthly_savings(inp)

    lo = Decimal("0")
    hi = Decimal("5000")
    found: Decimal | None = None

    for _ in range(20):  # 20 iterations of binary search
        mid = (lo + hi) / Decimal("2")
        test_inp = copy.deepcopy(inp)
        _add_savings_to_input(test_inp, mid)
        timeline = project_timeline(test_inp)

        # Check if goal is reached at target_year
        retirement_monthly = _get_retirement_income_at_year(timeline, target_year)
        if retirement_monthly is not None and retirement_monthly >= target:
            found = mid
            hi = mid
        else:
            lo = mid

    if found is None:
        return None

    found = found.quantize(Decimal("10"))  # Round to nearest 10€

    # Feasibility threshold
    feasibility = _classify_feasibility(found, [200, 500, 1000])

    return GoalSolution(
        lever="monthly_savings",
        label=f"Épargner {found}€/mois de plus",
        description=f"Passer de {current_savings}€ à {current_savings + found}€ d'épargne mensuelle",
        current_value=f"{current_savings}€/mois",
        required_value=f"{current_savings + found}€/mois",
        change_amount=f"+{found}€/mois",
        feasibility=feasibility,
        goal_year=target_year,
        goal_age=target_age,
    )


def _solve_expenses(
    inp: ProjectionInput,
    target: Decimal,
    target_year: int,
    target_age: int,
) -> GoalSolution | None:
    """Binary search: how much less monthly expenses to hit the goal?"""
    current = inp.monthly_expenses_total

    if current <= Decimal("0"):
        return None  # Nothing to reduce

    lo = Decimal("0")
    hi = min(current * Decimal("0.5"), Decimal("2000"))  # max 50% reduction or 2000€
    found: Decimal | None = None

    for _ in range(20):
        mid = (lo + hi) / Decimal("2")
        test_inp = copy.deepcopy(inp)
        test_inp.monthly_expenses_total = current - mid
        timeline = project_timeline(test_inp)

        retirement_monthly = _get_retirement_income_at_year(timeline, target_year)
        if retirement_monthly is not None and retirement_monthly >= target:
            found = mid
            hi = mid
        else:
            lo = mid

    if found is None:
        return None

    found = found.quantize(Decimal("10"))
    feasibility = _classify_feasibility(found, [200, 500, 1000])

    return GoalSolution(
        lever="monthly_expenses",
        label=f"Réduire les dépenses de {found}€/mois",
        description=f"Passer de {current}€ à {current - found}€ de dépenses mensuelles",
        current_value=f"{current}€/mois",
        required_value=f"{current - found}€/mois",
        change_amount=f"-{found}€/mois",
        feasibility=feasibility,
        goal_year=target_year,
        goal_age=target_age,
    )


def _solve_growth(
    inp: ProjectionInput,
    target: Decimal,
    target_year: int,
    target_age: int,
) -> GoalSolution | None:
    """Binary search: what growth rate is needed?"""
    current_rate = inp.growth_rate

    lo = current_rate
    hi = Decimal("0.15")  # 15% growth is extreme
    found: Decimal | None = None

    for _ in range(20):
        mid = (lo + hi) / Decimal("2")
        test_inp = copy.deepcopy(inp)
        test_inp.growth_rate = mid
        timeline = project_timeline(test_inp)

        retirement_monthly = _get_retirement_income_at_year(timeline, target_year)
        if retirement_monthly is not None and retirement_monthly >= target:
            found = mid
            hi = mid
        else:
            lo = mid

    if found is None:
        return None

    delta = ((found - current_rate) * Decimal("100")).quantize(Decimal("0.1"))
    feasibility = _classify_feasibility(delta, [Decimal("1"), Decimal("3"), Decimal("5")])

    return GoalSolution(
        lever="growth_rate",
        label=f"Augmenter la croissance CA de +{delta}%/an",
        description=f"Passer de {current_rate * 100:.0f}% à {found * 100:.1f}% de croissance annuelle",
        current_value=f"{current_rate * 100:.0f}%/an",
        required_value=f"{found * 100:.1f}%/an",
        change_amount=f"+{delta}%",
        feasibility=feasibility,
        goal_year=target_year,
        goal_age=target_age,
    )


def _solve_retirement_age(
    inp: ProjectionInput,
    target: Decimal,
) -> GoalSolution | None:
    """Linear search: work how many more years?

    Tests retirement age from current+1 up to current+10 years later.
    """
    for extra_years in range(1, 11):
        test_inp = copy.deepcopy(inp)
        test_inp.target_age = inp.target_age + extra_years
        timeline = project_timeline(test_inp)

        # Check if any accumulation year reaches the goal
        for t in timeline:
            if not t.is_retirement and t.goal_reached:
                # Found an accumulation year where goal was reached
                # This means working extra_years more works
                feasibility = _classify_feasibility(
                    Decimal(str(extra_years)),
                    [Decimal("1"), Decimal("3"), Decimal("5")],
                )
                return GoalSolution(
                    lever="retirement_age",
                    label=f"Travailler {extra_years} an{'s' if extra_years > 1 else ''} de plus",
                    description=f"Retraite à {inp.target_age + extra_years} ans au lieu de {inp.target_age}",
                    current_value=f"Retraite à {inp.target_age} ans",
                    required_value=f"Retraite à {inp.target_age + extra_years} ans",
                    change_amount=f"+{extra_years} an{'s' if extra_years > 1 else ''}",
                    feasibility=feasibility,
                    goal_year=inp.current_year + (inp.target_age + extra_years - inp.current_age),
                    goal_age=inp.target_age + extra_years,
                )

    return None


def _solve_allocation(
    inp: ProjectionInput,
    target: Decimal,
    target_year: int,
    target_age: int,
) -> GoalSolution | None:
    """Test: redirect 50% of savings to PEA (higher yield vehicle)."""
    test_inp = copy.deepcopy(inp)
    total = _total_monthly_savings(inp)
    if total <= Decimal("0"):
        return None

    # Redirect half to PEA
    redirect = (total * Decimal("0.5")).quantize(Decimal("0.01"))

    # Find current PEA allocation
    pea_alloc = test_inp.allocations.get("pea", {"balance": Decimal("0"), "monthly": Decimal("0")})
    test_inp.allocations["pea"] = {
        "balance": pea_alloc.get("balance", Decimal("0")),
        "monthly": pea_alloc.get("monthly", Decimal("0")) + redirect,
    }

    # Reduce other allocations proportionally
    for k, v in test_inp.allocations.items():
        if k != "pea" and v.get("monthly", Decimal("0")) > Decimal("0"):
            v["monthly"] = v["monthly"] * Decimal("0.5")

    timeline = project_timeline(test_inp)
    retirement_monthly = _get_retirement_income_at_year(timeline, target_year)

    if retirement_monthly is not None and retirement_monthly >= target:
        return GoalSolution(
            lever="allocation_pea",
            label="Rediriger 50% de l'épargne vers PEA",
            description=f"Allouer {redirect}€/mois au PEA au lieu des véhicules actuels",
            current_value="Allocation actuelle",
            required_value=f"PEA: {redirect}€/mois",
            change_amount=f"Rediriger {redirect}€/mois",
            feasibility="moderate",
            goal_year=target_year,
            goal_age=target_age,
        )

    return None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _total_monthly_savings(inp: ProjectionInput) -> Decimal:
    """Sum all monthly investment contributions."""
    return sum(
        (alloc.get("monthly", Decimal("0")) for alloc in inp.allocations.values()),
        Decimal("0"),
    )


def _get_retirement_income_at_year(
    timeline: list,
    target_year: int,
) -> Decimal | None:
    """Get retirement-relevant monthly income at a specific target year.

    Finds the last accumulation year before target_year and extracts
    retirement_monthly_income (passive + project_income/12 + pension/12).

    Args:
        timeline: Full projection timeline.
        target_year: The year to check.

    Returns:
        Retirement monthly income at target_year, or None if not found.
    """
    # Find the year entry matching target_year
    target_entry = next((t for t in timeline if t.year == target_year), None)
    if target_entry is None:
        return None

    # Compute retirement-relevant income at that year
    # passive monthly income
    passive = target_entry.passive_monthly
    # project income + pension (annual / 12)
    proj_inc = target_entry.project_income
    pension = target_entry.pension_annual

    return passive + (proj_inc + pension) / Decimal("12")


def _add_savings_to_input(inp: ProjectionInput, extra: Decimal) -> None:
    """Add extra monthly savings to the best available vehicle.

    Prefers PEA, then AV UC, then AV Euro, then Livret A.
    If no vehicles exist, creates a Livret A entry.

    Args:
        inp: ProjectionInput to modify (mutated in place).
        extra: Additional monthly savings amount.
    """
    from app.calculations.vehicles import VEHICLE_SPECS

    # Prefer: pea → av_uc → av_euro → livret_a
    preference = ["pea", "av_uc", "av_euro", "livret_a"]
    for vehicle in preference:
        if vehicle in inp.allocations:
            alloc = inp.allocations[vehicle]
            alloc["monthly"] = alloc.get("monthly", Decimal("0")) + extra
            return

    # No vehicle exists — add to Livret A
    inp.allocations["livret_a"] = {"monthly": extra, "balance": Decimal("0")}


def _classify_feasibility(
    value: Decimal,
    thresholds: list[Decimal],
) -> str:
    """Classify a change amount into a feasibility level.

    Args:
        value: The change amount (e.g., 200 for 200€/mois).
        thresholds: List of thresholds [easy_cap, moderate_cap, hard_cap].

    Returns:
        One of: "easy", "moderate", "hard", "extreme".
    """
    if value <= thresholds[0]:
        return "easy"
    if value <= thresholds[1]:
        return "moderate"
    if value <= thresholds[2]:
        return "hard"
    return "extreme"