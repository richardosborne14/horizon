"""
Projection engine — the heart of Horizon.

A pure calculation function that ingests all user data (profile, life entities,
recurring expenses, investments, projects, status change) and produces a
year-by-year projection from current age to target retirement age.

This is the most complex single piece of code in Horizon. It walks every year,
queries every data source, compounds every investment, ages every kid,
replaces every car, and produces a timeline the frontend renders as charts,
milestones, and a detailed table.

Design principles:
  - Pure function — all data passed in, no DB access. Testable without setup.
  - All Decimal — never float. Financial precision is mandatory.
  - Deterministic — same inputs always produce same outputs.
  - Reads existing calculation modules (ae_rates, caf, constants, vehicles).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.calculations.ae_rates import get_ae_rate, get_cfe_estimate
from app.calculations.caf import estimate_monthly_caf
from app.calculations.constants import INFLATION_SCALES
from app.calculations.vehicles import VEHICLE_SPECS

logger = logging.getLogger(__name__)

# Default current year — computed at call time for testability.
# Tests may override by passing a custom current_year in ProjectionInput.
_DEFAULT_CURRENT_YEAR = datetime.now().year

# ├─────────────────────────────────────────────────────────────────────────────
# │ Input / Output data structures
# ├─────────────────────────────────────────────────────────────────────────────


@dataclass
class ProjectionInput:
    """Flat data object the engine receives.

    The API layer (TASK-4.2) assembles this from the DB.
    All monetary values are Decimal.
    """

    # Identity
    current_age: int
    target_age: int
    current_year: int = _DEFAULT_CURRENT_YEAR  # pin for testability

    # Revenue
    monthly_gross: Decimal = Decimal("0")
    growth_rate: Decimal = Decimal("0")
    ae_activity_type: str = "bnc_non_reglementee"

    # Expenses (pre-summed by API layer from profile.monthly_expenses JSONB)
    monthly_expenses_total: Decimal = Decimal("0")

    # Scale
    scale: str = "moderate"  # "optimistic" | "moderate" | "pessimistic"

    # Life entities — pre-processed into a flat cost schedule
    # list of: {"entity_type", "entity_name", "entity_age_at_start",
    #           "cost_events": [{"label","from_age","to_age","amount","frequency","is_active"},...]}
    life_entities: list[dict[str, Any]] = field(default_factory=list)

    # Recurring expenses — list of: {"label","annual_amount","from_year","to_year"}
    recurring_expenses: list[dict[str, Any]] = field(default_factory=list)

    # Investments — dict of vehicle_key → {"balance": Decimal, "monthly": Decimal}
    allocations: dict[str, dict[str, Decimal]] = field(default_factory=dict)

    # Projects — list of dicts with type "invest" or "event"
    projects: list[dict[str, Any]] = field(default_factory=list)

    # CAF
    kids_birth_dates: list[date] = field(default_factory=list)
    caf_override_monthly: Decimal | None = None  # null = auto-estimate
    household_income_for_caf: Decimal = Decimal("0")

    # Tax breaks
    cesu_annual: Decimal = Decimal("0")
    charity_annual: Decimal = Decimal("0")

    # Status change simulation
    status_change_enabled: bool = False
    status_change_year: int | None = None
    status_change_savings: Decimal | None = None

    # Goal
    monthly_revenue_goal: Decimal | None = None


@dataclass
class YearProjection:
    """A single year in the 30-year projection timeline.

    Serialised as JSON via the API layer (Pydantic models in schemas/).
    All monetary fields are Decimal — serialise as strings for JSON.
    """

    year: int
    age: int

    # Revenue
    gross_annual: Decimal = Decimal("0")
    ae_rate: Decimal = Decimal("0")
    charges: Decimal = Decimal("0")  # gross × ae_rate
    cfe: Decimal = Decimal("0")

    # Expenses
    base_expenses: Decimal = Decimal("0")  # monthly × 12, inflation-adjusted
    kid_expenses: Decimal = Decimal("0")
    pet_expenses: Decimal = Decimal("0")
    car_expenses: Decimal = Decimal("0")
    tech_expenses: Decimal = Decimal("0")
    recurring_expenses: Decimal = Decimal("0")
    project_expenses: Decimal = Decimal("0")  # investment running costs + event one-time
    project_income: Decimal = Decimal("0")  # investment rental income

    # Income additions
    caf_annual: Decimal = Decimal("0")
    tax_credits: Decimal = Decimal("0")  # CESU + charity
    status_bonus: Decimal = Decimal("0")

    # Net
    total_income: Decimal = Decimal("0")  # gross + project_income + caf + tax_credits
    total_outgoing: Decimal = Decimal("0")  # charges + cfe + all expense categories
    net_annual: Decimal = Decimal("0")  # total_income - total_outgoing + status_bonus

    # Investments
    year_invested: Decimal = Decimal("0")
    year_returns: Decimal = Decimal("0")
    total_wealth: Decimal = Decimal("0")  # sum of all vehicle balances

    # Derived
    passive_monthly: Decimal = Decimal("0")  # total_wealth × 4% / 12
    total_monthly_income: Decimal = Decimal("0")  # (gross + project_income + caf) / 12 + passive
    goal_reached: bool = False


# ├─────────────────────────────────────────────────────────────────────────────
# │ Main projection function
# ├─────────────────────────────────────────────────────────────────────────────


def project_timeline(inp: ProjectionInput) -> list[YearProjection]:
    """Compute a year-by-year projection from current_age to target_age.

    Walks every year, compounding investments, aging life entities,
    inflating expenses, applying tax credits, estimating CAF, and
    checking goal attainment.

    Args:
        inp: A fully assembled ProjectionInput dataclass.

    Returns:
        List of YearProjection, one per year from current_age to target_age
        exclusive (e.g., age 40→70 = 30 entries for ages 40 through 69).
        The final year projection's wealth and passive income represent
        the state at retirement.

    Raises:
        ValueError: If scale is not one of the known inflation scales.
        ValueError: If current_age >= target_age.
    """
    if inp.current_age >= inp.target_age:
        raise ValueError(
            f"current_age ({inp.current_age}) must be less than "
            f"target_age ({inp.target_age})"
        )

    years = inp.target_age - inp.current_age
    scale_config = INFLATION_SCALES.get(inp.scale)
    if scale_config is None:
        raise ValueError(
            f"Unknown inflation scale: {inp.scale!r}. "
            f"Valid scales: {list(INFLATION_SCALES.keys())}"
        )

    inflation_rate = scale_config["inflation"]
    cost_living_rate = scale_config["cost_living"]

    # Initialise balances dict — beginning-of-year balances per vehicle
    balances: dict[str, Decimal] = {}
    for vk, alloc in inp.allocations.items():
        balances[vk] = alloc.get("balance", Decimal("0"))

    timeline: list[YearProjection] = []

    for y in range(years):
        year = inp.current_year + y
        age = inp.current_age + y
        infl = (Decimal("1") + inflation_rate) ** y
        cost_factor = (Decimal("1") + cost_living_rate) ** y

        # ── Revenue ──────────────────────────────────────────────────
        gross = inp.monthly_gross * Decimal("12") * (
            (Decimal("1") + inp.growth_rate) ** y
        )
        ae_rate = get_ae_rate(inp.ae_activity_type, year)
        charges = gross * ae_rate
        cfe = get_cfe_estimate(year, inflation_rate)

        # ── Status change ────────────────────────────────────────────
        status_bonus = Decimal("0")
        if (
            inp.status_change_enabled
            and inp.status_change_year is not None
            and year >= inp.status_change_year
        ):
            status_bonus = inp.status_change_savings or Decimal("0")

        # ── Base expenses ────────────────────────────────────────────
        base_exp = inp.monthly_expenses_total * Decimal("12") * cost_factor

        # ── Life entity expenses ─────────────────────────────────────
        kid_exp = pet_exp = car_exp = tech_exp = Decimal("0")
        for entity in inp.life_entities:
            entity_age = entity.get("entity_age_at_start", 0) + y
            entity_type = entity.get("entity_type", "")
            for evt in entity.get("cost_events", []):
                if not evt.get("is_active", True):
                    continue
                from_age = int(evt.get("from_age", 0))
                to_age = int(evt.get("to_age", 0))
                if entity_age < from_age or entity_age > to_age:
                    continue
                amount = Decimal(str(evt.get("amount", 0))) * infl
                frequency = evt.get("frequency", "monthly")
                if frequency == "monthly":
                    amount *= Decimal("12")
                elif frequency == "annual":
                    pass  # amount stays annual
                elif frequency == "once":
                    # Only fire in the exact year the entity hits from_age
                    if entity_age != from_age:
                        continue
                # Route to the right bucket
                if entity_type == "kid":
                    kid_exp += amount
                elif entity_type == "pet":
                    pet_exp += amount
                elif entity_type == "car":
                    car_exp += amount
                elif entity_type == "tech":
                    tech_exp += amount

        # ── Recurring expenses ───────────────────────────────────────
        rec_exp = Decimal("0")
        for r in inp.recurring_expenses:
            from_year = int(r.get("from_year", 0))
            to_year = int(r.get("to_year", 0))
            if from_year <= year <= to_year:
                rec_exp += Decimal(str(r.get("annual_amount", 0))) * infl

        # ── Projects ─────────────────────────────────────────────────
        proj_exp = Decimal("0")
        proj_inc = Decimal("0")
        for p in inp.projects:
            ptype = p.get("type", "")
            if ptype == "invest":
                start_year = p.get("start_year")
                if start_year is None or year < int(start_year):
                    continue
                if year == int(start_year):
                    proj_exp += Decimal(str(p.get("purchase_cost", 0)))
                owned = year - int(start_year)
                if owned > 0:
                    inc = Decimal(str(p.get("annual_income", 0))) * (
                        (Decimal("1.02")) ** owned
                    )
                    exp = Decimal(str(p.get("annual_expenses", 0))) * infl
                    tax_rate = Decimal(str(p.get("tax_rate", "0.30")))
                    taxable = max(Decimal("0"), inc - exp)
                    tax = taxable * tax_rate
                    proj_inc += inc
                    proj_exp += exp + tax
            elif ptype == "event":
                event_year = p.get("event_year")
                if event_year is not None and year == int(event_year):
                    proj_exp += Decimal(str(p.get("event_cost", 0)))

        # ── CAF ──────────────────────────────────────────────────────
        if inp.caf_override_monthly is not None:
            # Override: revalorise at 1.5%/year (same as CAF's internal rate)
            kids_under_20 = _count_kids_under(inp.kids_birth_dates, year, 20)
            if kids_under_20 > 0:
                caf = inp.caf_override_monthly * Decimal("12") * (
                    (Decimal("1.015")) ** y
                )
            else:
                caf = Decimal("0")
        else:
            caf_monthly = estimate_monthly_caf(
                kids_birth_dates=inp.kids_birth_dates,
                reference_year=year,
                annual_household_income=(
                    inp.household_income_for_caf
                    if inp.household_income_for_caf > 0
                    else gross
                ),
            )
            caf = caf_monthly * Decimal("12")

        # ── Tax credits ──────────────────────────────────────────────
        cesu_credit = min(
            inp.cesu_annual * infl * Decimal("0.5"), Decimal("6000")
        )
        charity_credit = min(
            inp.charity_annual * infl * Decimal("0.66"), Decimal("20000")
        )
        tax_credits = cesu_credit + charity_credit

        # ── Net ──────────────────────────────────────────────────────
        total_income = gross + proj_inc + caf + tax_credits
        total_outgoing = (
            charges
            + cfe
            + base_exp
            + kid_exp
            + pet_exp
            + car_exp
            + tech_exp
            + rec_exp
            + proj_exp
        )
        net = total_income - total_outgoing + status_bonus

        # ── Investments ──────────────────────────────────────────────
        year_invested = Decimal("0")
        year_returns = Decimal("0")
        for vk, alloc in inp.allocations.items():
            monthly = alloc.get("monthly", Decimal("0"))
            if monthly <= 0:
                continue
            spec = VEHICLE_SPECS.get(vk)
            if not spec:
                continue
            bal = balances.get(vk, Decimal("0"))
            contrib = monthly * Decimal("12")
            # Effective real return: rate minus 25% of inflation, floor at 0.5%
            eff_rate = max(
                Decimal("0.005"),
                spec["rate"] - inflation_rate * Decimal("0.25"),
            )
            returns = bal * eff_rate
            if spec.get("tax_free", False):
                net_ret = returns
            else:
                net_ret = returns * (
                    Decimal("1") - Decimal(str(spec.get("tax_rate", 0)))
                )
            ceiling = spec.get("ceiling")
            new_bal = bal + contrib + net_ret
            if ceiling is not None:
                new_bal = min(new_bal, ceiling * infl)
            balances[vk] = new_bal
            year_invested += contrib
            year_returns += net_ret

        wealth = sum(balances.values(), Decimal("0"))
        passive = wealth * Decimal("0.04") / Decimal("12")
        total_monthly = (gross + proj_inc + caf) / Decimal("12") + passive

        timeline.append(
            YearProjection(
                year=year,
                age=age,
                gross_annual=gross.quantize(Decimal("0.01")),
                ae_rate=ae_rate,
                charges=charges.quantize(Decimal("0.01")),
                cfe=cfe.quantize(Decimal("0.01")),
                base_expenses=base_exp.quantize(Decimal("0.01")),
                kid_expenses=kid_exp.quantize(Decimal("0.01")),
                pet_expenses=pet_exp.quantize(Decimal("0.01")),
                car_expenses=car_exp.quantize(Decimal("0.01")),
                tech_expenses=tech_exp.quantize(Decimal("0.01")),
                recurring_expenses=rec_exp.quantize(Decimal("0.01")),
                project_expenses=proj_exp.quantize(Decimal("0.01")),
                project_income=proj_inc.quantize(Decimal("0.01")),
                caf_annual=caf.quantize(Decimal("0.01")),
                tax_credits=tax_credits.quantize(Decimal("0.01")),
                status_bonus=status_bonus.quantize(Decimal("0.01")),
                total_income=total_income.quantize(Decimal("0.01")),
                total_outgoing=total_outgoing.quantize(Decimal("0.01")),
                net_annual=net.quantize(Decimal("0.01")),
                year_invested=year_invested.quantize(Decimal("0.01")),
                year_returns=year_returns.quantize(Decimal("0.01")),
                total_wealth=wealth.quantize(Decimal("0.01")),
                passive_monthly=passive.quantize(Decimal("0.01")),
                total_monthly_income=total_monthly.quantize(Decimal("0.01")),
                goal_reached=bool(
                    inp.monthly_revenue_goal is not None
                    and inp.monthly_revenue_goal > 0
                    and total_monthly >= inp.monthly_revenue_goal
                ),
            )
        )

    return timeline


# ├─────────────────────────────────────────────────────────────────────────────
# │ Helper functions
# ├─────────────────────────────────────────────────────────────────────────────


def compute_milestones(timeline: list[YearProjection]) -> list[dict[str, Any]]:
    """Find the first year where wealth crosses each milestone threshold.

    Args:
        timeline: Full projection timeline from project_timeline().

    Returns:
        List of {"label": str, "year": int, "age": int} for each
        milestone reached during the projection period. Thresholds:
        100k€, 250k€, 500k€, 1M€.
    """
    targets: list[tuple[int, str]] = [
        (100_000, "100k€"),
        (250_000, "250k€"),
        (500_000, "500k€"),
        (1_000_000, "1M€"),
    ]
    milestones: list[dict[str, Any]] = []
    for amount, label in targets:
        hit = next(
            (t for t in timeline if t.total_wealth >= Decimal(str(amount))),
            None,
        )
        if hit:
            milestones.append({"label": label, "year": hit.year, "age": hit.age})
    return milestones


def find_goal_year(timeline: list[YearProjection]) -> dict[str, int] | None:
    """Find the first year where the monthly income goal is reached.

    Args:
        timeline: Full projection timeline from project_timeline().

    Returns:
        {"year": int, "age": int} if goal is reached, None otherwise.
    """
    hit = next((t for t in timeline if t.goal_reached), None)
    if hit:
        return {"year": hit.year, "age": hit.age}
    return None


def compute_summary(
    timeline: list[YearProjection],
) -> dict[str, Any]:
    """Compute summary statistics from a full projection timeline.

    Args:
        timeline: Full projection timeline from project_timeline().

    Returns:
        Dict with keys:
          - years: total projected years
          - final_wealth: total wealth at last year
          - final_passive_monthly: passive income at last year
          - total_invested: sum of all contributions
          - total_returns: sum of all investment returns
          - goal_year: {"year", "age"} or None
          - milestones: list of milestone dicts
    """
    if not timeline:
        return {
            "years": 0,
            "final_wealth": "0.00",
            "final_passive_monthly": "0.00",
            "total_invested": "0.00",
            "total_returns": "0.00",
            "goal_year": None,
            "milestones": [],
        }

    last = timeline[-1]
    total_invested = sum((t.year_invested for t in timeline), Decimal("0"))
    total_returns = sum((t.year_returns for t in timeline), Decimal("0"))

    return {
        "years": len(timeline),
        "final_wealth": str(last.total_wealth),
        "final_passive_monthly": str(last.passive_monthly),
        "total_invested": str(total_invested.quantize(Decimal("0.01"))),
        "total_returns": str(total_returns.quantize(Decimal("0.01"))),
        "goal_year": find_goal_year(timeline),
        "milestones": compute_milestones(timeline),
    }


def _count_kids_under(
    kids_birth_dates: list[date],
    year: int,
    max_age: int,
) -> int:
    """Count how many kids are under max_age on January 1st of the given year.

    Uses the same age calculation as the CAF module:
    age = year - birth_year, adjusted for month/day.

    Args:
        kids_birth_dates: List of birth dates.
        year: Reference year.
        max_age: Exclusive maximum age (kids at this age or older don't count).

    Returns:
        Number of kids under max_age.
    """
    jan_1 = date(year, 1, 1)
    count = 0
    for birth_date in kids_birth_dates:
        age = jan_1.year - birth_date.year
        if (jan_1.month, jan_1.day) < (birth_date.month, birth_date.day):
            age -= 1
        if age < max_age:
            count += 1
    return count