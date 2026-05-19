"""
Retirement readiness score (TASK-5.5) — synthesizes the projection into a single
0–100 score with 6 weighted components.

Design:
  - Pure function, no DB access. Testable standalone.
  - Six components weighted: goal coverage (30%), wealth durability (25%),
    savings rate (15%), diversification (10%), growth trajectory (10%),
    buffer adequacy (10%).
  - Score bands: Fragile (0–20), En construction (21–40), Sur la bonne voie (41–60),
    Solide (61–80), Excellent (81–100).

Integration:
  - Called by the projection router. Response includes readiness alongside insights.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


# ── Data structures ──────────────────────────────────────────────────────


@dataclass
class ReadinessScore:
    """Retirement readiness score with component breakdown."""

    score: int  # 0–100
    label: str  # "Fragile" | "En construction" | "Sur la bonne voie" | "Solide" | "Excellent"
    color: str  # rose | amber | yellow | teal | emerald
    components: dict[str, int]  # sub-scores per component
    summary: str  # one-sentence explanation


# ── Score bands ──────────────────────────────────────────────────────────

_BANDS: list[dict[str, Any]] = [
    {"min": 0, "max": 20, "label": "Fragile", "color": "rose",
     "summary": "Votre situation nécessite une action rapide."},
    {"min": 21, "max": 40, "label": "En construction", "color": "amber",
     "summary": "Les fondations sont là, mais il y a du travail."},
    {"min": 41, "max": 60, "label": "Sur la bonne voie", "color": "yellow",
     "summary": "Vous progressez, continuez sur cette lancée."},
    {"min": 61, "max": 80, "label": "Solide", "color": "teal",
     "summary": "Votre plan tient la route."},
    {"min": 81, "max": 100, "label": "Excellent", "color": "emerald",
     "summary": "Vous êtes en très bonne position."},
]


def _band_for(score: int) -> dict[str, Any]:
    """Return the band dict for a given score."""
    for band in _BANDS:
        if band["min"] <= score <= band["max"]:
            return band
    return _BANDS[-1]


# ── Public API ───────────────────────────────────────────────────────────


def compute_readiness_score(
    timeline: list[Any],
    summary: dict[str, Any],
    profile_data: dict[str, Any],
    allocations: list[dict[str, Any]],
    monthly_revenue_goal: Decimal | None = None,
    extra_liquid: Decimal | None = None,
) -> ReadinessScore:
    """Compute retirement readiness score from projection data.

    Args:
        timeline: Full projection timeline (list of YearProjection).
        summary: Dict from compute_summary().
        profile_data: Flat dict with monthly_gross, growth_rate, target_age, current_age.
        allocations: List of allocation dicts with vehicle_key, monthly, balance.
        monthly_revenue_goal: User's monthly revenue goal (None = no goal set).
        extra_liquid: Additional liquid cash (from net worth snapshot) for buffer adequacy.

    Returns:
        ReadinessScore with score, label, color, components, summary.
    """
    if not timeline:
        return ReadinessScore(
            score=0,
            label="Fragile",
            color="rose",
            components={
                "goal_coverage": 0,
                "wealth_durability": 0,
                "savings_rate": 0,
                "diversification": 0,
                "growth_trajectory": 0,
                "buffer_adequacy": 0,
            },
            summary="Complétez votre profil pour obtenir un score.",
        )

    # ── Component 1: Goal coverage (30%) ────────────────────────────
    goal_coverage = _compute_goal_coverage(
        timeline, summary, monthly_revenue_goal
    )

    # ── Component 2: Wealth durability (25%) ────────────────────────
    wealth_durability = _compute_wealth_durability(summary, timeline)

    # ── Component 3: Savings rate (15%) ─────────────────────────────
    savings_rate = _compute_savings_rate(timeline, allocations)

    # ── Component 4: Diversification (10%) ──────────────────────────
    diversification = _compute_diversification(allocations)

    # ── Component 5: Growth trajectory (10%) ────────────────────────
    growth_trajectory = _compute_growth_trajectory(timeline)

    # ── Component 6: Buffer adequacy (10%) ──────────────────────────
    buffer_adequacy = _compute_buffer_adequacy(allocations, timeline, extra_liquid)

    # Weighted average
    weights = {
        "goal_coverage": 30,
        "wealth_durability": 25,
        "savings_rate": 15,
        "diversification": 10,
        "growth_trajectory": 10,
        "buffer_adequacy": 10,
    }
    components = {
        "goal_coverage": goal_coverage,
        "wealth_durability": wealth_durability,
        "savings_rate": savings_rate,
        "diversification": diversification,
        "growth_trajectory": growth_trajectory,
        "buffer_adequacy": buffer_adequacy,
    }

    # If no goal, skip goal_coverage and reweight
    has_goal = monthly_revenue_goal is not None and monthly_revenue_goal > 0
    if not has_goal:
        weights.pop("goal_coverage")
        components.pop("goal_coverage")
        total_weight = sum(weights.values())
        # Normalize remaining weights
        for k in weights:
            weights[k] = int(weights[k] / total_weight * 100)
        # Redistribute: 100 total
        total = sum(weights.values())
        weights = {k: int(v / total * 100) for k, v in weights.items()}

    weighted_sum = sum(
        components[k] * weights[k] for k in components
    )
    total_weight = sum(weights.values())
    score = min(100, max(0, int(weighted_sum / total_weight))) if total_weight > 0 else 0

    band = _band_for(score)

    # Build summary sentence
    if score <= 20:
        synopsis = "Votre situation est fragile. Concentrez-vous sur la constitution d'un fonds d'urgence et l'augmentation de votre épargne."
    elif score <= 40:
        synopsis = "Les bases sont posées. Augmentez votre taux d'épargne et diversifiez vos placements pour passer au niveau supérieur."
    elif score <= 60:
        synopsis = "Vous êtes sur la bonne voie. Continuez d'épargner régulièrement et vérifiez que vos placements sont bien diversifiés."
    elif score <= 80:
        synopsis = "Votre plan est solide. Quelques ajustements sur l'allocation ou la croissance pourraient vous rapprocher de l'excellence."
    else:
        synopsis = "Excellent ! Votre situation est très favorable. Restez discipliné et ajustez votre plan chaque année."

    return ReadinessScore(
        score=score,
        label=band["label"],
        color=band["color"],
        components=components,
        summary=synopsis,
    )


# ── Component functions ──────────────────────────────────────────────────


def _compute_goal_coverage(
    timeline: list[Any],
    summary: dict[str, Any],
    monthly_revenue_goal: Decimal | None,
) -> int:
    """Goal coverage (30%): can retirement income meet the goal?

    100 = income ≥ 120% of goal. 0 = income < 30% of goal. Linear in between.
    No goal → 0 (caller should handle reweighting).
    """
    if monthly_revenue_goal is None or monthly_revenue_goal <= 0:
        return 0

    # Get retirement monthly income from the first retirement year
    retirement_entries = [t for t in timeline if getattr(t, "is_retirement", False)]
    if not retirement_entries:
        # No retirement entries — use last accumulation year's passive income
        if not timeline:
            return 0
        last = timeline[-1]
        retirement_income = getattr(last, "passive_monthly", Decimal("0"))
    else:
        first_ret = retirement_entries[0]
        proj_inc = getattr(first_ret, "project_income", Decimal("0"))
        pension = getattr(first_ret, "pension_annual", Decimal("0"))
        retirement_income = (proj_inc + pension) / Decimal("12")

    ratio = retirement_income / monthly_revenue_goal

    if ratio >= Decimal("1.2"):
        return 100
    if ratio <= Decimal("0.3"):
        return 0
    # Linear between 0.3 and 1.2 → map to 0–100
    return int(float((ratio - Decimal("0.3")) / Decimal("0.9") * 100))


def _compute_wealth_durability(
    summary: dict[str, Any],
    timeline: list[Any] | None = None,
) -> int:
    """Wealth durability (25%): how long does wealth last post-retirement?

    100 = lasts to 95+. 0 = runs out within 5 years of retirement.
    Linear in between.

    Args:
        summary: compute_summary() result.
        timeline: Full projection timeline (needed for accurate retirement age).
                  AUDIT-8.2.4: was hardcoded to 70, now derived from timeline.
    """
    exhaustion_age = summary.get("wealth_exhaustion_age")
    if exhaustion_age is None:
        return 100  # never runs out in simulation

    if exhaustion_age >= 95:
        return 100

    # AUDIT-8.2.4: derive retirement_start from the timeline so users
    # targeting 62 or 75 get a correct durability calculation.
    retirement_start = 70  # sensible default if timeline not available
    if timeline:
        retirement_entry = next(
            (t for t in timeline if getattr(t, "is_retirement", False)), None
        )
        if retirement_entry:
            retirement_start = getattr(retirement_entry, "age", 70)
    years_after_retirement = exhaustion_age - retirement_start
    if years_after_retirement <= 5:
        return 0
    if years_after_retirement >= 25:
        return 100
    # Linear: 5→0, 25→100
    return int((years_after_retirement - 5) / 20 * 100)


def _compute_savings_rate(
    timeline: list[Any],
    allocations: list[dict[str, Any]],
) -> int:
    """Savings rate (15%): current savings as % of net income after charges.

    Denominator = gross_annual - charges - cfe (income available before
    living expenses). This is the meaningful figure — it shows what fraction
    of disposable income is saved, not what fraction of the surplus is saved.

    AUDIT-8.2.4 fix: old denominator was net_annual (surplus after ALL expenses)
    which produced wildly inflated rates (e.g. 5k savings / 14k surplus = 35%,
    but actual savings rate vs net income = 5k / 59k = 8.5%).

    100 = ≥ 25%. 0 = < 5%. Linear in between.
    """
    if not timeline or not allocations:
        return 0

    t0 = timeline[0]
    gross_annual = getattr(t0, "gross_annual", Decimal("0"))
    charges = getattr(t0, "charges", Decimal("0"))
    cfe = getattr(t0, "cfe", Decimal("0"))
    # Net income after charges = take-home before living expenses
    net_income_after_charges = gross_annual - charges - cfe
    if net_income_after_charges <= 0:
        return 0

    total_monthly_savings = sum(
        Decimal(str(a.get("monthly", 0))) for a in allocations
    )
    total_annual_savings = total_monthly_savings * Decimal("12")
    rate = total_annual_savings / net_income_after_charges

    if rate >= Decimal("0.25"):
        return 100
    if rate <= Decimal("0.05"):
        return 0
    return int(float(rate / Decimal("0.25") * 100))


def _compute_diversification(allocations: list[dict[str, Any]]) -> int:
    """Diversification (10%): investment spread across vehicles.

    100 = 4+ vehicles with meaningful allocation (>5% of total). 0 = 1 vehicle.
    Each meaningful vehicle = 25 points.
    """
    if not allocations:
        return 0

    total_monthly = sum(
        Decimal(str(a.get("monthly", 0))) for a in allocations
    )
    if total_monthly <= 0:
        return 0

    meaningful = sum(
        1 for a in allocations
        if Decimal(str(a.get("monthly", 0))) > total_monthly * Decimal("0.05")
    )
    return min(100, meaningful * 25)


def _compute_growth_trajectory(timeline: list[Any]) -> int:
    """Growth trajectory (10%): is wealth growing faster than expenses?

    100 = real growth > 3%/year. 0 = wealth declining.
    Compare wealth at year 5 vs year 1, annualized.
    """
    if len(timeline) < 5:
        return 50  # not enough data, neutral

    early = timeline[1] if len(timeline) > 1 else timeline[0]
    later_idx = min(5, len(timeline) - 1)
    later = timeline[later_idx]

    early_wealth = getattr(early, "total_wealth", Decimal("0"))
    later_wealth = getattr(later, "total_wealth", Decimal("0"))

    if early_wealth <= 0:
        return 0

    years = later_idx - 1 or 1
    ratio = float(later_wealth / early_wealth)
    annual_growth = ratio ** (1.0 / years) - 1.0

    if annual_growth >= 0.03:
        return 100
    if annual_growth <= 0:
        return 0
    # Linear: 0→0, 0.03→100
    return min(100, int(annual_growth / 0.03 * 100))


def _compute_buffer_adequacy(
    allocations: list[dict[str, Any]],
    timeline: list[Any],
    extra_liquid: Decimal | None = None,
) -> int:
    """Buffer adequacy (10%): emergency fund vs 6 months expenses.

    100 = ≥ 6 months in liquid (Livret A + LDDS + AV euro + cash reserves).
    0 = < 1 month. Linear in between.
    """
    # Sum liquid balances from investment vehicles
    liquid = Decimal("0")
    for a in allocations:
        if a.get("vehicle_key") in ("livret_a", "ldds", "av_euro"):
            liquid += Decimal(str(a.get("balance", 0)))

    # Add extra liquid (cash reserves from net worth snapshot)
    if extra_liquid is not None and extra_liquid > 0:
        liquid += extra_liquid

    # Monthly expenses from first year
    if not timeline:
        return 0

    t0 = timeline[0]
    total_outgoing = getattr(t0, "total_outgoing", Decimal("0"))
    if total_outgoing <= 0:
        total_outgoing = Decimal("12")  # fallback: assume 1€/month to avoid div-zero

    monthly_expenses = total_outgoing / Decimal("12")
    if monthly_expenses <= 0:
        return 0

    months_buffer = float(liquid / monthly_expenses)

    if months_buffer >= 6:
        return 100
    if months_buffer <= 1:
        return 0
    return min(100, int(months_buffer / 6 * 100))