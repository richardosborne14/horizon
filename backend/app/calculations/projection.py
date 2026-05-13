"""
Projection engine — the heart of Horizon.

A pure calculation function that ingests all user data (profile, life entities,
recurring expenses, investments, projects, status change) and produces a
year-by-year projection from current age through retirement to age 95.

Sprint 5 extends the engine with post-retirement drawdown modeling.
After the target retirement age, work income drops to zero, expenses
continue (inflation-adjusted), pension income begins, and savings are
drawn down to cover the gap.

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
from app.calculations.income_tax import compute_ir
from app.calculations.vehicles import VEHICLE_SPECS, VEHICLE_ORDER

logger = logging.getLogger(__name__)

# Default current year — computed at call time for testability.
# Tests may override by passing a custom current_year in ProjectionInput.
_DEFAULT_CURRENT_YEAR = datetime.now().year

# Post-retirement defaults
_DEFAULT_POST_RETIREMENT_YEARS = 25  # simulate to age 95 (retire at 70 + 25)
_AGE_CAP = 95  # hard cap — projection never goes beyond this age


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

    # Post-retirement
    post_retirement_years: int = _DEFAULT_POST_RETIREMENT_YEARS
    pension_monthly: Decimal = Decimal("0")  # placeholder until TASK-5.3

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

    # Loans (Sprint 6 — fixed nominal monthly payments, terminate at end_date)
    # list of: {"label","monthly_payment","start_date","end_date","insurance_monthly"}
    loans: list[dict[str, Any]] = field(default_factory=list)

    # Goal
    monthly_revenue_goal: Decimal | None = None

    # Income Tax (TASK-7.12)
    tax_parts: Decimal = Decimal("1")  # Quotient familial parts (1=seul, 2=couple, +0.5/enfant)
    versement_liberatoire: bool = False
    spouse_annual_income: Decimal = Decimal("0")  # Spouse salary (CDI/CDD)
    other_annual_income: Decimal = Decimal("0")  # Dividends, rental, etc.

    # ── Spouse (TASK-7.8) ──────────────────────────────────────────────
    spouse_monthly_gross: Decimal = Decimal("0")
    spouse_growth_rate: Decimal = Decimal("0.03")
    spouse_ae_type: str | None = None  # None = salaried (no AE cotisations)
    spouse_pension_monthly: Decimal = Decimal("0")
    spouse_retirement_age: int | None = None  # None = same as user

    # ── CC (conjointe collaboratrice) ──────────────────────────────────
    cc_annual_cotisation: Decimal = Decimal("0")

    # ── Income sources (replaces flat CA growth) ───────────────────────
    income_sources: list[dict] | None = None
    # Each: {earner, label, amount, frequency, start_date, end_date,
    #        annual_growth_rate, is_ae_revenue}
    # If None → use monthly_gross with growth_rate (backward compat)

    # ── Property (TASK-7.16) ────────────────────────────────────────────
    property_value: Decimal = Decimal("0")           # Current estimated value
    property_appreciation_rate: Decimal = Decimal("0.02")  # Annual appreciation
    downsize_enabled: bool = False                   # Enable downsizing simulation
    downsize_year: int | None = None                  # Year of downsizing
    downsize_target_value: Decimal = Decimal("0")     # Value of replacement property


@dataclass
class YearProjection:
    """A single year in the projection timeline (accumulation + post-retirement).

    Serialised as JSON via the API layer (Pydantic models in schemas/).
    All monetary fields are Decimal — serialise as strings for JSON.
    """

    year: int
    age: int

    # Phase indicator
    is_retirement: bool = False  # True for years after target retirement age

    # Revenue
    gross_annual: Decimal = Decimal("0")
    ae_rate: Decimal = Decimal("0")
    charges: Decimal = Decimal("0")  # gross × ae_rate
    cfe: Decimal = Decimal("0")

    # Expenses
    base_expenses: Decimal = Decimal("0")  # monthly × 12, inflation-adjusted
    loan_expenses: Decimal = Decimal("0")  # fixed nominal loan payments (Sprint 6)
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

    # Post-retirement specific
    pension_monthly: Decimal = Decimal("0")  # state pension estimate
    pension_annual: Decimal = Decimal("0")  # pension_monthly × 12
    withdrawal_annual: Decimal = Decimal("0")  # amount withdrawn from savings this year

    # Net
    total_income: Decimal = Decimal("0")  # gross + project_income + caf + tax_credits + pension
    total_outgoing: Decimal = Decimal("0")  # charges + cfe + all expense categories
    net_annual: Decimal = Decimal("0")  # total_income - total_outgoing + status_bonus

    # Investments
    year_invested: Decimal = Decimal("0")
    year_returns: Decimal = Decimal("0")
    total_wealth: Decimal = Decimal("0")  # sum of all vehicle balances

    # Income Tax (TASK-7.12)
    ir_annual: Decimal = Decimal("0")  # Impôt sur le revenu for this year
    ir_monthly: Decimal = Decimal("0")  # IR / 12
    taux_effectif_ir: Decimal = Decimal("0")  # Effective tax rate this year

    # Derived
    passive_monthly: Decimal = Decimal("0")  # total_wealth × 4% / 12
    total_monthly_income: Decimal = Decimal("0")  # (gross + project_income + caf + pension) / 12 + passive
    goal_reached: bool = False

    # ── Property (TASK-7.16) ────────────────────────────────────────────
    property_value: Decimal = Decimal("0")      # Current property value this year
    downsize_freed: Decimal = Decimal("0")      # Freed capital (non-zero only in downsize year)


# ├─────────────────────────────────────────────────────────────────────────────
# │ Main projection function
# ├─────────────────────────────────────────────────────────────────────────────


def project_timeline(inp: ProjectionInput) -> list[YearProjection]:
    """Compute a year-by-year projection from current_age through retirement.

    Phase 1 (accumulation): current_age → target_age.
    Phase 2 (post-retirement): target_age → target_age + post_retirement_years.

    In Phase 2, work income drops to zero, expenses continue (inflation-adjusted),
    pension income begins, and savings are drawn down to cover the shortfall.

    Args:
        inp: A fully assembled ProjectionInput dataclass.

    Returns:
        List of YearProjection, one per year from current_age through
        retirement phase (up to age 95 max).

    Raises:
        ValueError: If scale is not one of the known inflation scales.
        ValueError: If current_age >= target_age.
    """
    if inp.current_age >= inp.target_age:
        raise ValueError(
            f"current_age ({inp.current_age}) must be less than "
            f"target_age ({inp.target_age})"
        )

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

    # ──────────────────────────────────────────────────────────────────────
    # Phase 1: Accumulation (working years)
    # ──────────────────────────────────────────────────────────────────────
    accumulation_years = inp.target_age - inp.current_age
    post_retirement_years = min(
        inp.post_retirement_years,
        _AGE_CAP - inp.target_age,
    )

    for y in range(accumulation_years):
        entry = _compute_accumulation_year(
            inp=inp,
            y=y,
            infl_rate=inflation_rate,
            cost_living_rate=cost_living_rate,
            balances=balances,
        )
        timeline.append(entry)

    # ──────────────────────────────────────────────────────────────────────
    # Phase 2: Post-retirement (drawdown years)
    # ──────────────────────────────────────────────────────────────────────
    for y in range(post_retirement_years):
        entry = _compute_retirement_year(
            inp=inp,
            y=accumulation_years + y,
            infl_rate=inflation_rate,
            cost_living_rate=cost_living_rate,
            balances=balances,
        )
        timeline.append(entry)

        # Stop early if wealth is exhausted (cannot draw more)
        if entry.total_wealth <= 0:
            break

    return timeline


# ├─────────────────────────────────────────────────────────────────────────────
# │ Phase 1: Accumulation year computation
# ├─────────────────────────────────────────────────────────────────────────────


def _compute_accumulation_year(
    inp: ProjectionInput,
    y: int,
    infl_rate: Decimal,
    cost_living_rate: Decimal,
    balances: dict[str, Decimal],
) -> YearProjection:
    """Compute a single year in the accumulation (working) phase.

    Same logic as Sprint 4 projection engine, refactored into a helper
    so the post-retirement phase can reuse expense/investment computation.
    """
    year = inp.current_year + y
    age = inp.current_age + y
    infl = (Decimal("1") + infl_rate) ** y
    cost_factor = (Decimal("1") + cost_living_rate) ** y

    # ── Revenue (TASK-7.8: income sources or flat CA) ────────────────
    onetime = Decimal("0")
    spouse_income = Decimal("0")
    spouse_charges = Decimal("0")

    if inp.income_sources:
        user_ae_income = compute_income_for_year(
            inp.income_sources, year, "user", ae_only=True,
            current_year=inp.current_year,
            growth_rate=inp.growth_rate,
        )
        user_non_ae_income = (
            compute_income_for_year(
                inp.income_sources, year, "user", ae_only=False,
                current_year=inp.current_year,
                growth_rate=Decimal("0"),
            )
            - user_ae_income
        )
        spouse_income = compute_income_for_year(
            inp.income_sources, year, "spouse",
            current_year=inp.current_year,
            growth_rate=Decimal("0"),
        )
        onetime = compute_onetime_income_for_year(
            inp.income_sources, year,
        )
        gross = user_ae_income  # AE cotisations apply to this
    else:
        # Backward compat: flat CA with growth
        gross = inp.monthly_gross * Decimal("12") * (
            (Decimal("1") + inp.growth_rate) ** y
        )
        user_non_ae_income = Decimal("0")
        # Spouse income handled below in spouse block
        spouse_income = Decimal("0")
        onetime = Decimal("0")

    ae_rate = get_ae_rate(inp.ae_activity_type, year)
    charges = gross * ae_rate
    cfe = get_cfe_estimate(year, infl_rate)

    # ── Spouse income and cotisations (TASK-7.8) ─────────────────────
    spouse_ret_age = inp.spouse_retirement_age or inp.target_age
    spouse_age = inp.current_age + y
    spouse_retired = spouse_age >= spouse_ret_age

    if not inp.income_sources:
        # Backward compat: determine spouse income from flat fields
        if spouse_retired:
            spouse_income = inp.spouse_pension_monthly * Decimal("12")
        elif inp.spouse_monthly_gross > 0:
            spouse_income = inp.spouse_monthly_gross * Decimal("12") * (
                (Decimal("1") + inp.spouse_growth_rate) ** y
            )
    else:
        # Income sources: spouse_income already computed above
        if spouse_retired:
            spouse_income = inp.spouse_pension_monthly * Decimal("12")
            spouse_charges = Decimal("0")

    # Compute spouse cotisations if working
    if not spouse_retired and spouse_income > 0:
        spouse_charges = _compute_spouse_charges(inp, spouse_income, year)

    # ── CC cotisation as expense (TASK-7.8) ──────────────────────────
    cc_expense = Decimal("0")
    if inp.cc_annual_cotisation > 0 and not spouse_retired:
        cc_expense = inp.cc_annual_cotisation

    # ── Status change ────────────────────────────────────────────────
    status_bonus = Decimal("0")
    if (
        inp.status_change_enabled
        and inp.status_change_year is not None
        and year >= inp.status_change_year
    ):
        status_bonus = inp.status_change_savings or Decimal("0")

    # ── Expenses ─────────────────────────────────────────────────────
    base_exp, kid_exp, pet_exp, car_exp, tech_exp = _compute_life_entity_expenses(
        inp, y, infl
    )
    base_exp += inp.monthly_expenses_total * Decimal("12") * cost_factor

    # Loan expenses (fixed nominal, NOT inflation-adjusted — TASK-6.3)
    loan_exp = _compute_loan_expenses(inp, year)

    # Recurring expenses
    rec_exp = _compute_recurring_expenses(inp, year, infl)

    # Projects
    proj_exp, proj_inc = _compute_project_cashflow(inp, year, infl)

    # ── CAF / Tax credits ────────────────────────────────────────────
    caf = _compute_caf(inp, y, gross + user_non_ae_income + spouse_income, year)
    tax_credits = _compute_tax_credits(inp, infl)
    pension = Decimal("0")  # no pension during working years

    # ── Income Tax (IR) ──────────────────────────────────────────────
    ir_result = compute_ir(
        ae_ca_annual=gross,
        ae_activity_type=inp.ae_activity_type,
        salary_annual=spouse_income if not inp.spouse_ae_type else inp.spouse_annual_income,
        other_income_annual=inp.other_annual_income + user_non_ae_income,
        tax_parts=inp.tax_parts,
        cesu_credit=min(
            inp.cesu_annual * infl * Decimal("0.5"), Decimal("6000")
        ),
        charity_reduction=min(
            inp.charity_annual * infl * Decimal("0.66"), Decimal("20000")
        ),
        has_vl=inp.versement_liberatoire,
    )
    ir_annual = Decimal(ir_result["ir_net"])
    ir_monthly = Decimal(ir_result["monthly_ir"])
    taux_effectif = Decimal(ir_result["taux_effectif"])

    # ── Net ──────────────────────────────────────────────────────────
    total_income = (
        gross + user_non_ae_income + spouse_income
        + onetime + proj_inc + caf + tax_credits
    )
    total_outgoing = (
        charges + spouse_charges + cc_expense + cfe
        + base_exp + kid_exp + pet_exp
        + car_exp + tech_exp + rec_exp + proj_exp + loan_exp
        + ir_annual
    )
    net = total_income - total_outgoing + status_bonus

    # ── Investments (contributions + returns) ────────────────────────
    year_invested, year_returns = _compute_investment_growth(
        inp, balances, infl_rate, infl, y=y
    )

    # ── Surplus reinvestment ────────────────────────────────────────
    # Any positive net (income - expenses - charges) that isn't already
    # structured as a monthly allocation gets reinvested at 50% into the
    # highest-yield available vehicle. Without this, changes to growth_rate
    # or expenses produce zero delta in sensitivity analysis because the
    # extra cash never reaches investments.
    surplus_for_investment = max(Decimal("0"), net) * Decimal("0.5")
    if surplus_for_investment > 0 and inp.allocations:
        # Find the highest-rate existing vehicle to receive surplus
        best_vk = max(
            inp.allocations.keys(),
            key=lambda k: VEHICLE_SPECS.get(k, {}).get("rate", Decimal("0")),
        )
        balances[best_vk] = balances.get(best_vk, Decimal("0")) + surplus_for_investment
        year_invested += surplus_for_investment

    # ── Property appreciation and downsizing (TASK-7.16) ────────────
    current_property = Decimal("0")
    downsize_freed = Decimal("0")

    if inp.property_value > 0:
        from app.calculations.property import project_property_value, compute_downsize_capital

        years_from_start = y
        current_property = project_property_value(
            inp.property_value, inp.property_appreciation_rate, years_from_start,
        )

        # Downsizing event
        if (
            inp.downsize_enabled
            and inp.downsize_year is not None
            and year == inp.downsize_year
        ):
            freed_capital = compute_downsize_capital(
                current_property, inp.downsize_target_value,
            )
            if freed_capital > 0:
                # Add freed capital to investments (distribute to AV or PEA)
                if "av_euro" in balances:
                    balances["av_euro"] += freed_capital
                elif "pea" in balances:
                    balances["pea"] += freed_capital
                else:
                    balances["av_euro"] = freed_capital
                downsize_freed = freed_capital

            # Update property value to replacement
            current_property = inp.downsize_target_value

    wealth = sum(balances.values(), Decimal("0"))
    passive = wealth * Decimal("0.04") / Decimal("12")
    total_monthly = (gross + proj_inc + caf) / Decimal("12") + passive

    # Retirement-relevant monthly income excludes work salary and CAF
    # (both drop to zero at retirement). The goal is "à la retraite."
    retirement_monthly_income = passive + (proj_inc + pension) / Decimal("12")

    return YearProjection(
        year=year,
        age=age,
        is_retirement=False,
        gross_annual=gross.quantize(Decimal("0.01")),
        ae_rate=ae_rate,
        charges=charges.quantize(Decimal("0.01")),
        cfe=cfe.quantize(Decimal("0.01")),
        base_expenses=base_exp.quantize(Decimal("0.01")),
        loan_expenses=loan_exp.quantize(Decimal("0.01")),
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
        pension_monthly=Decimal("0"),
        pension_annual=Decimal("0"),
        withdrawal_annual=Decimal("0"),
        total_income=total_income.quantize(Decimal("0.01")),
        total_outgoing=total_outgoing.quantize(Decimal("0.01")),
        net_annual=net.quantize(Decimal("0.01")),
        ir_annual=ir_annual.quantize(Decimal("0.01")),
        ir_monthly=ir_monthly.quantize(Decimal("0.01")),
        taux_effectif_ir=taux_effectif.quantize(Decimal("0.0001")),
        year_invested=year_invested.quantize(Decimal("0.01")),
        year_returns=year_returns.quantize(Decimal("0.01")),
        total_wealth=wealth.quantize(Decimal("0.01")),
        passive_monthly=passive.quantize(Decimal("0.01")),
        total_monthly_income=total_monthly.quantize(Decimal("0.01")),
        goal_reached=bool(
            inp.monthly_revenue_goal is not None
            and inp.monthly_revenue_goal > 0
            and retirement_monthly_income >= inp.monthly_revenue_goal
        ),
        property_value=current_property.quantize(Decimal("0.01")),
        downsize_freed=downsize_freed.quantize(Decimal("0.01")),
    )


# ├─────────────────────────────────────────────────────────────────────────────
# │ Phase 2: Post-retirement year computation
# ├─────────────────────────────────────────────────────────────────────────────


def _compute_retirement_year(
    inp: ProjectionInput,
    y: int,
    infl_rate: Decimal,
    cost_living_rate: Decimal,
    balances: dict[str, Decimal],
) -> YearProjection:
    """Compute a single year in the post-retirement (drawdown) phase.

    Work income = 0. Pension begins. Expenses continue with inflation.
    If expenses > income from pension + project income, withdraw the
    shortfall from savings (liquid accounts first).
    """
    year = inp.current_year + y
    age = inp.current_age + y
    infl = (Decimal("1") + infl_rate) ** y
    cost_factor = (Decimal("1") + cost_living_rate) ** y

    # ── No work income ───────────────────────────────────────────────
    gross = Decimal("0")
    charges = Decimal("0")
    cfe = Decimal("0")
    status_bonus = Decimal("0")

    # ── Pension income (TASK-7.8: household = user + spouse) ─────────
    pension_monthly = inp.pension_monthly
    spouse_pension_monthly = inp.spouse_pension_monthly
    household_pension_monthly = pension_monthly + spouse_pension_monthly
    pension_annual = household_pension_monthly * Decimal("12")

    # ── Expenses (same structure as accumulation, minus work-related) ─
    base_exp, kid_exp, pet_exp, car_exp, tech_exp = _compute_life_entity_expenses(
        inp, y, infl
    )
    base_exp += inp.monthly_expenses_total * Decimal("12") * cost_factor

    rec_exp = _compute_recurring_expenses(inp, year, infl)
    proj_exp, proj_inc = _compute_project_cashflow(inp, year, infl)

    caf = Decimal("0")  # no CAF after retirement
    tax_credits = Decimal("0")  # no CESU/charity credits after retirement

    # ── Income vs expenses ──────────────────────────────────────────
    total_income = proj_inc + pension_annual
    total_outgoing = (
        base_exp + kid_exp + pet_exp + car_exp
        + tech_exp + rec_exp + proj_exp
    )

    # ── Compound remaining investments (no new contributions) ────────
    year_invested = Decimal("0")
    year_returns = Decimal("0")
    for vk in list(balances.keys()):
        if vk not in VEHICLE_SPECS:
            continue
        spec = VEHICLE_SPECS[vk]
        bal = balances.get(vk, Decimal("0"))
        eff_rate = max(
            Decimal("0.005"),
            spec["rate"] - infl_rate * Decimal("0.25"),
        )
        returns = bal * eff_rate
        if spec.get("tax_free", False):
            net_ret = returns
        else:
            net_ret = returns * (
                Decimal("1") - Decimal(str(spec.get("tax_rate", 0)))
            )
        balances[vk] = bal + net_ret  # no contributions, only returns
        year_returns += net_ret

    # ── Tax-optimized drawdown (TASK-7.13) ───────────────────────────
    # Replaces both the 4% rule AND the simple shortfall withdrawal.
    # Draws from PEA → AV → SCPI → PER with tax optimization
    # and maintains a 6-month liquidity buffer in Livret A/LDDS.
    monthly_exp = total_outgoing / Decimal("12")
    withdrawal = Decimal("0")
    wealth = sum(balances.values(), Decimal("0"))

    try:
        from app.calculations.drawdown import compute_drawdown_for_year

        drawdown = compute_drawdown_for_year(
            balances=balances,
            monthly_need=inp.monthly_revenue_goal or monthly_exp,
            monthly_expenses=monthly_exp,
            tax_parts=inp.tax_parts,
            is_couple=(inp.spouse_monthly_gross > Decimal("0")),
        )
        # Replace balances with drawdown's remaining_balances
        for vehicle, new_bal_str in drawdown["remaining_balances"].items():
            balances[vehicle] = Decimal(new_bal_str)
        passive = Decimal(drawdown["net_income_monthly"])
        withdrawal = (
            Decimal(drawdown["total_withdrawn"])
            - Decimal(drawdown["total_tax"])
        )
    except Exception:
        # Fallback to simple withdrawal + 4% rule
        shortfall = total_outgoing - total_income
        if shortfall > 0:
            withdrawal = _withdraw_from_savings(balances, shortfall)
        passive = max(Decimal("0"), wealth * Decimal("0.04") / Decimal("12"))

    # Total net for the year
    net = total_income - total_outgoing + withdrawal  # withdrawal fills the gap

    total_monthly = (proj_inc + pension_annual) / Decimal("12") + passive

    # ── Property appreciation and downsizing (TASK-7.16) ────────────
    # Continue property appreciation through retirement. Downsizing
    # can also happen during retirement years.
    current_property = Decimal("0")
    downsize_freed = Decimal("0")

    if inp.property_value > 0:
        from app.calculations.property import project_property_value, compute_downsize_capital

        years_from_start = y
        current_property = project_property_value(
            inp.property_value, inp.property_appreciation_rate, years_from_start,
        )

        # Downsizing event (can happen in retirement)
        if (
            inp.downsize_enabled
            and inp.downsize_year is not None
            and year == inp.downsize_year
        ):
            freed_capital = compute_downsize_capital(
                current_property, inp.downsize_target_value,
            )
            if freed_capital > 0:
                # Add freed capital to investments
                if "av_euro" in balances:
                    balances["av_euro"] += freed_capital
                elif "pea" in balances:
                    balances["pea"] += freed_capital
                else:
                    balances["av_euro"] = freed_capital
                downsize_freed = freed_capital

            # Update property value to replacement
            current_property = inp.downsize_target_value

    # Recompute wealth after potential downsize injection
    wealth = sum(balances.values(), Decimal("0"))

    return YearProjection(
        year=year,
        age=age,
        is_retirement=True,
        gross_annual=Decimal("0"),
        ae_rate=Decimal("0"),
        charges=Decimal("0"),
        cfe=Decimal("0"),
        base_expenses=base_exp.quantize(Decimal("0.01")),
        loan_expenses=Decimal("0"),
        kid_expenses=kid_exp.quantize(Decimal("0.01")),
        pet_expenses=pet_exp.quantize(Decimal("0.01")),
        car_expenses=car_exp.quantize(Decimal("0.01")),
        tech_expenses=tech_exp.quantize(Decimal("0.01")),
        recurring_expenses=rec_exp.quantize(Decimal("0.01")),
        project_expenses=proj_exp.quantize(Decimal("0.01")),
        project_income=proj_inc.quantize(Decimal("0.01")),
        caf_annual=Decimal("0"),
        tax_credits=Decimal("0"),
        status_bonus=Decimal("0"),
        pension_monthly=pension_monthly.quantize(Decimal("0.01")),
        pension_annual=pension_annual.quantize(Decimal("0.01")),
        withdrawal_annual=withdrawal.quantize(Decimal("0.01")),
        total_income=total_income.quantize(Decimal("0.01")),
        total_outgoing=total_outgoing.quantize(Decimal("0.01")),
        net_annual=net.quantize(Decimal("0.01")),
        year_invested=Decimal("0"),
        year_returns=year_returns.quantize(Decimal("0.01")),
        total_wealth=wealth.quantize(Decimal("0.01")),
        passive_monthly=passive.quantize(Decimal("0.01")),
        total_monthly_income=total_monthly.quantize(Decimal("0.01")),
        goal_reached=False,
        property_value=current_property.quantize(Decimal("0.01")),
        downsize_freed=downsize_freed.quantize(Decimal("0.01")),
    )


# ├─────────────────────────────────────────────────────────────────────────────
# │ Withdrawal engine
# ├─────────────────────────────────────────────────────────────────────────────


def _withdraw_from_savings(
    balances: dict[str, Decimal],
    needed: Decimal,
) -> Decimal:
    """Withdraw from savings using bucket priority: liquid accounts first.

    Priority order: Livret A → LDDS → AV euro → AV UC → PEA → SCPI → PER.
    PER is unlocked at retirement (included in drawdown pool).

    Args:
        balances: Current balances dict (mutated in place).
        needed: Total amount to withdraw.

    Returns:
        The amount actually withdrawn (may be less than needed if wealth is exhausted).
    """
    # Withdrawal priority: liquid → less liquid
    priority = [
        "livret_a",
        "ldds",
        "av_euro",
        "av_uc",
        "pea",
        "scpi",
        "per",
    ]

    withdrawn = Decimal("0")
    remaining = needed

    for vk in priority:
        if remaining <= 0:
            break
        bal = balances.get(vk, Decimal("0"))
        if bal <= 0:
            continue
        take = min(bal, remaining)
        balances[vk] = bal - take
        withdrawn += take
        remaining -= take

    return withdrawn


# ├─────────────────────────────────────────────────────────────────────────────
# │ Expense sub-computations (shared between phases)
# ├─────────────────────────────────────────────────────────────────────────────


def _compute_life_entity_expenses(
    inp: ProjectionInput,
    y: int,
    infl: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Compute expenses from life entities (kids, pets, cars, tech).

    Returns:
        Tuple of (base_exp_additional, kid_exp, pet_exp, car_exp, tech_exp).
        base_exp_additional is always 0 (handled separately).
    """
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
                pass
            elif frequency == "once":
                if entity_age != from_age:
                    continue
            if entity_type == "kid":
                kid_exp += amount
            elif entity_type == "pet":
                pet_exp += amount
            elif entity_type == "car":
                car_exp += amount
            elif entity_type == "tech":
                tech_exp += amount
    return Decimal("0"), kid_exp, pet_exp, car_exp, tech_exp


def _compute_loan_expenses(
    inp: ProjectionInput,
    year: int,
) -> Decimal:
    """Compute total loan expenses active in the given year.

    Loans are fixed nominal payments — NOT inflation-adjusted.
    A loan is active if year falls within [start_date.year, end_date.year].
    Insurance is added to the monthly payment.

    Args:
        inp: Projection input with loans list.
        year: The projection year.

    Returns:
        Annual loan expense total (fixed nominal).
    """
    loan_exp = Decimal("0")
    for loan in inp.loans:
        start_date_obj = loan.get("start_date")
        end_date_obj = loan.get("end_date")

        # Parse date strings or date objects
        if isinstance(start_date_obj, str):
            start_date_obj = date.fromisoformat(start_date_obj)
        if isinstance(end_date_obj, str):
            end_date_obj = date.fromisoformat(end_date_obj)

        if start_date_obj is None:
            continue

        start_year = start_date_obj.year

        # If no end_date, treat as active forever (like the flat credit field)
        if end_date_obj is None:
            end_year = 9999
        else:
            end_year = end_date_obj.year

        if start_year <= year <= end_year:
            monthly = Decimal(str(loan.get("monthly_payment", 0)))
            insurance = Decimal(str(loan.get("insurance_monthly", 0)))
            loan_exp += (monthly + insurance) * Decimal("12")

    return loan_exp


def _compute_recurring_expenses(
    inp: ProjectionInput,
    year: int,
    infl: Decimal,
) -> Decimal:
    """Compute recurring expenses active in the given year."""
    rec_exp = Decimal("0")
    for r in inp.recurring_expenses:
        from_year = int(r.get("from_year", 0))
        to_year = int(r.get("to_year", 0))
        if from_year <= year <= to_year:
            rec_exp += Decimal(str(r.get("annual_amount", 0))) * infl
    return rec_exp


def _compute_project_cashflow(
    inp: ProjectionInput,
    year: int,
    infl: Decimal,
) -> tuple[Decimal, Decimal]:
    """Compute project expenses and income for the given year.

    Returns:
        Tuple of (project_expenses, project_income).
    """
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
    return proj_exp, proj_inc


def _compute_caf(
    inp: ProjectionInput,
    y: int,
    gross: Decimal,
    year: int,
) -> Decimal:
    """Compute CAF (family allowance) for the given year."""
    if inp.caf_override_monthly is not None:
        kids_under_20 = _count_kids_under(inp.kids_birth_dates, year, 20)
        if kids_under_20 > 0:
            return inp.caf_override_monthly * Decimal("12") * (
                (Decimal("1.015")) ** y
            )
        return Decimal("0")

    caf_monthly = estimate_monthly_caf(
        kids_birth_dates=inp.kids_birth_dates,
        reference_year=year,
        annual_household_income=(
            inp.household_income_for_caf
            if inp.household_income_for_caf > 0
            else gross
        ),
    )
    return caf_monthly * Decimal("12")


def _compute_tax_credits(inp: ProjectionInput, infl: Decimal) -> Decimal:
    """Compute CESU and charity tax credits."""
    cesu_credit = min(
        inp.cesu_annual * infl * Decimal("0.5"), Decimal("6000")
    )
    charity_credit = min(
        inp.charity_annual * infl * Decimal("0.66"), Decimal("20000")
    )
    return cesu_credit + charity_credit


def _compute_investment_growth(
    inp: ProjectionInput,
    balances: dict[str, Decimal],
    inflation_rate: Decimal,
    infl: Decimal,
    y: int = 0,
) -> tuple[Decimal, Decimal]:
    """Compound investments for one year (Sprint 5 refined + 5.10 tax by holding period).

    Refinements:
    - Regulated vehicles track inflation in optimistic/moderate.
    - Nominal ceilings (not inflation-adjusted).
    - Overflow redirect when a vehicle hits its ceiling.
    - Tax rate differentiates by holding period:
      * Pre-maturity (PEA < 5yr, AV < 8yr): PFU 30% on gains
      * Post-maturity: only PS 17.2% on gains
      * Existing balances assume mature (held long enough).

    Args:
        inp: Projection input with allocations, scale, etc.
        balances: Current vehicle balances (mutated in place).
        inflation_rate: Annual inflation rate for this scale.
        infl: Cumulative inflation factor (unused, kept for signature compatibility).
        y: Year index in projection (0 = first year). Used to determine holding period.

    Returns:
        Tuple of (year_invested, year_returns).
    """
    year_invested = Decimal("0")
    year_returns = Decimal("0")
    overflow: dict[str, Decimal] = {}  # overflow to be applied after loop

    for vk, alloc in inp.allocations.items():
        monthly = alloc.get("monthly", Decimal("0"))
        spec = VEHICLE_SPECS.get(vk)
        if not spec:
            continue
        bal = balances.get(vk, Decimal("0"))
        if monthly <= 0 and bal <= 0:
            # Skip vehicles with no money at all — no contributions and no
            # existing balance to compound.
            continue
        has_existing = bal > Decimal("0")  # non-zero starting balance
        contrib = monthly * Decimal("12")

        # Regulated vehicles: rate tracks inflation in non-pessimistic scales
        if spec.get("regulated", False):
            if inp.scale == "pessimistic":
                eff_rate = spec["rate"]
            else:
                eff_rate = max(spec["rate"], inflation_rate)
        else:
            # Market-based returns: nominal rate minus 25% of inflation
            eff_rate = max(
                Decimal("0.005"),
                spec["rate"] - inflation_rate * Decimal("0.25"),
            )

        returns = bal * eff_rate

        # ── Tax treatment by holding period (TASK-5.10) ────────────
        if spec.get("tax_free", False):
            net_ret = returns
        else:
            # Determine tax rate based on vehicle maturity rules
            tax_rate = Decimal(str(spec.get("tax_rate", Decimal("0.172"))))
            # PFU (30%) = 17.2% PS + 12.8% IR; PS only (17.2%) after maturity
            PFU = Decimal("0.300")
            PS_ONLY = Decimal("0.172")

            if vk == "pea":
                # PEA: after 5 years, only PS on gains. Pre-maturity: PFU.
                # existing balance implies already mature
                if has_existing or y >= 5:
                    tax_rate = PS_ONLY
                else:
                    tax_rate = PFU
            elif vk in ("av_euro", "av_uc"):
                # AV: after 8 years, PS on gains (with 4600€ abattement).
                # Pre-maturity: PFU (30%). Existing balance implies mature.
                if has_existing or y >= 8:
                    tax_rate = PS_ONLY
                else:
                    tax_rate = PFU
            elif vk == "scpi":
                # SCPI: always PFU (real estate income taxed at full rate)
                tax_rate = PFU
            elif vk == "per":
                # PER: contributions were tax-deductible; exit taxed as income.
                # Blended estimate: ~20% on gains at withdrawal.
                tax_rate = Decimal("0.200")
            else:
                # Default: use the spec's tax_rate (already PS_ONLY in most cases)
                tax_rate = Decimal(str(spec.get("tax_rate", tax_rate)))

            net_ret = returns * (Decimal("1") - tax_rate)

        ceiling = spec.get("ceiling")
        new_bal = bal + contrib + net_ret

        if ceiling is not None:
            # Nominal ceiling (not inflation-adjusted) for regulated vehicles
            if new_bal > ceiling:
                overflow_vk = spec.get("overflow_target")
                if overflow_vk and overflow_vk in VEHICLE_SPECS:
                    over = new_bal - ceiling
                    overflow[overflow_vk] = overflow.get(overflow_vk, Decimal("0")) + over
                    new_bal = ceiling
                else:
                    new_bal = ceiling  # cap without overflow

        balances[vk] = new_bal
        year_invested += contrib
        year_returns += net_ret

    # Apply overflow amounts to target vehicles
    for target_vk, amount in overflow.items():
        balances[target_vk] = balances.get(target_vk, Decimal("0")) + amount

    return year_invested, year_returns


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

    Only checks accumulation-phase years (is_retirement=False).

    Args:
        timeline: Full projection timeline from project_timeline().

    Returns:
        {"year": int, "age": int} if goal is reached, None otherwise.
    """
    hit = next(
        (t for t in timeline if t.goal_reached and not t.is_retirement),
        None,
    )
    if hit:
        return {"year": hit.year, "age": hit.age}
    return None


def find_wealth_exhaustion_age(
    timeline: list[YearProjection],
) -> int | None:
    """Find the age at which total wealth first hits zero or below.

    Args:
        timeline: Full projection timeline.

    Returns:
        Age at wealth exhaustion, or None if wealth never hits zero in the timeline.
    """
    for t in timeline:
        if t.total_wealth <= 0 and t.is_retirement:
            return t.age
    return None


def compute_summary(
    timeline: list[YearProjection],
) -> dict[str, Any]:
    """Compute summary statistics from a full projection timeline.

    Extended in Sprint 5 with post-retirement fields:
    wealth_exhaustion_age, retirement_monthly_income, retirement_monthly_gap.

    Args:
        timeline: Full projection timeline from project_timeline().

    Returns:
        Dict with keys:
          - years: total projected years
          - final_wealth: total wealth at retirement start (peak, before drawdown)
          - final_passive_monthly: passive income at retirement start
          - total_invested: sum of all contributions
          - total_returns: sum of all investment returns
          - goal_year: {"year", "age"} or None
          - milestones: list of milestone dicts
          - wealth_exhaustion_age: age when wealth hits zero, or None
          - retirement_monthly_income: income at retirement start
          - retirement_monthly_gap: gap between income and expenses at retirement
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
            "wealth_exhaustion_age": None,
            "retirement_monthly_income": "0.00",
            "retirement_monthly_gap": "0.00",
        }

    total_invested = sum((t.year_invested for t in timeline), Decimal("0"))
    total_returns = sum((t.year_returns for t in timeline), Decimal("0"))

    # Use retirement-start wealth (peak) rather than final-year wealth
    # because the drawdown phase may exhaust all savings.
    # The last accumulation year holds peak pre-retirement wealth.
    accumulation_only = [t for t in timeline if not t.is_retirement]
    peak = accumulation_only[-1] if accumulation_only else timeline[-1]

    # Find first retirement year for income/gap stats
    retirement_entries = [t for t in timeline if t.is_retirement]
    retirement_monthly_income = Decimal("0")
    retirement_monthly_gap = Decimal("0")

    if retirement_entries:
        first_ret = retirement_entries[0]
        # Monthly retirement income: (project_income + pension) / 12
        retirement_monthly_income = (
            first_ret.project_income + first_ret.pension_annual
        ) / Decimal("12")
        # Monthly gap: income - expenses
        retirement_monthly_gap = (
            first_ret.total_income - first_ret.total_outgoing
        ) / Decimal("12")

    # Include property value in total wealth (not just investments)
    peak_property = Decimal(peak.property_value) if hasattr(peak, "property_value") and peak.property_value else Decimal("0")
    peak_total_wealth = Decimal(peak.total_wealth) + peak_property

    return {
        "years": len(timeline),
        "final_wealth": str(peak_total_wealth.quantize(Decimal("0.01"))),
        "final_passive_monthly": str(peak.passive_monthly),
        "total_invested": str(total_invested.quantize(Decimal("0.01"))),
        "total_returns": str(total_returns.quantize(Decimal("0.01"))),
        "goal_year": find_goal_year(timeline),
        "milestones": compute_milestones(timeline),
        "wealth_exhaustion_age": find_wealth_exhaustion_age(timeline),
        "retirement_monthly_income": str(
            retirement_monthly_income.quantize(Decimal("0.01"))
        ),
        "retirement_monthly_gap": str(
            retirement_monthly_gap.quantize(Decimal("0.01"))
        ),
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


# ├─────────────────────────────────────────────────────────────────────────────
# │ Income source helpers (TASK-7.8)
# ├─────────────────────────────────────────────────────────────────────────────


def compute_income_for_year(
    sources: list[dict],
    year: int,
    earner: str,
    ae_only: bool = False,
    current_year: int = 2026,
    growth_rate: Decimal = Decimal("0"),
) -> Decimal:
    """Sum active income sources for a given year and earner.

    Args:
        sources: List of income source dicts with keys:
            earner, label, amount, frequency, start_date, end_date,
            annual_growth_rate, is_ae_revenue.
        year: The projection year.
        earner: "user" or "spouse".
        ae_only: If True, only include is_ae_revenue=True sources.
        current_year: The current year (for growth indexing).
        growth_rate: Global AE growth rate to apply when a source has
            no per-source annual_growth_rate. Only applied to AE sources.

    Returns:
        Annual income from matching sources.
    """
    total = Decimal("0")
    for src in sources:
        if src.get("earner") != earner:
            continue
        if ae_only and not src.get("is_ae_revenue", True):
            continue

        # Check if source is active this year
        start_date_str = src.get("start_date")
        end_date_str = src.get("end_date")
        start_year = int(start_date_str[:4]) if start_date_str else 0
        end_year = int(end_date_str[:4]) if end_date_str else 9999
        if year < start_year or year > end_year:
            continue

        # Skip one-time sources (handled separately)
        if src.get("frequency") == "one_time":
            continue

        amount = Decimal(str(src.get("amount", "0")))
        # Apply growth from source start.
        # Per-source annual_growth_rate takes priority.
        # For AE sources with no per-source growth, fall back to the
        # global growth_rate (from the user's growth_preset).
        per_source_growth = Decimal(str(src.get("annual_growth_rate") or "0"))
        is_ae = src.get("is_ae_revenue", True)
        if per_source_growth > 0:
            growth = per_source_growth
        elif is_ae and growth_rate > 0:
            growth = growth_rate
        else:
            growth = Decimal("0")
        years_active = max(0, year - max(start_year, current_year))
        grown = amount * ((Decimal("1") + growth) ** years_active)

        if src.get("frequency") == "monthly":
            total += grown * Decimal("12")
        elif src.get("frequency") == "annual":
            total += grown

    return total


def compute_onetime_income_for_year(
    sources: list[dict],
    year: int,
) -> Decimal:
    """Sum one-time income events occurring in a given year.

    Args:
        sources: List of income source dicts (same shape as compute_income_for_year).
        year: The projection year.

    Returns:
        Sum of one-time income amounts for this year.
    """
    total = Decimal("0")
    for src in sources:
        if src.get("frequency") != "one_time":
            continue
        start_date_str = src.get("start_date")
        if start_date_str and int(start_date_str[:4]) == year:
            total += Decimal(str(src.get("amount", "0")))
    return total


def _compute_spouse_charges(
    inp: ProjectionInput,
    spouse_annual: Decimal,
    year: int,
) -> Decimal:
    """Compute social charges for spouse income.

    If spouse is AE (spouse_ae_type is set), use AE rates.
    Otherwise, use simplified salaried rate (23%).

    Args:
        inp: Projection input.
        spouse_annual: Spouse annual income.
        year: The projection year.

    Returns:
        Social charges amount.
    """
    if inp.spouse_ae_type and spouse_annual > 0:
        ae_rate = get_ae_rate(inp.spouse_ae_type, year)
        return spouse_annual * ae_rate
    elif spouse_annual > 0:
        # Simplified salaried rate: ~23% (salarial + patronal)
        return spouse_annual * Decimal("0.23")
    return Decimal("0")
