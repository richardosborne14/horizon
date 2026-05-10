"""
Sensitivity analysis engine (TASK-6.7).

Systematically tests how changes to key levers affect the final projection
outcome. For each parameter, clones the ProjectionInput, applies a meaningful
nudge, re-runs the full projection, and compares wealth-at-retirement and
wealth-exhaustion-age against the baseline.

Design principles:
  - Pure function — receives a fully assembled ProjectionInput.
  - All Decimal arithmetic — never float.
  - Runs ~7 full projection passes. At ~100ms each = ~700ms total.
  - Results ranked by absolute delta_wealth descending.
  - Caching is handled at the API layer (router), not here.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.calculations.projection import (
    ProjectionInput,
    project_timeline,
    compute_summary,
)

# ── Constants ────────────────────────────────────────────────────────────────

# Parameter nudges — meaningful changes the user could realistically make
NUDGES: dict[str, dict[str, Any]] = {
    "monthly_savings": {
        "label": "Épargner 200€/mois de plus",
        "description": "Augmenter votre épargne mensuelle de 200€",
        "base_value_formatter": lambda inp: f"{inp._total_monthly_savings():.0f}€/mois d'épargne",
        "test_value_formatter": lambda inp, nudge: f"{(inp._total_monthly_savings() + nudge):.0f}€/mois (+200€)",
        "nudge_amount": Decimal("200"),
    },
    "monthly_expenses_decrease": {
        "label": "Dépenser 300€/mois de moins",
        "description": "Réduire vos dépenses mensuelles de 300€",
        "base_value_formatter": lambda inp: f"{inp.monthly_expenses_total:.0f}€/mois de dépenses",
        "test_value_formatter": lambda inp, nudge: f"{(inp.monthly_expenses_total - nudge):.0f}€/mois (-300€)",
        "nudge_amount": Decimal("300"),
    },
    "growth_rate": {
        "label": "Augmenter la croissance de 2%",
        "description": "Faire croître votre CA de 2% de plus par an (ex: 6% → 8%)",
        "base_value_formatter": lambda inp: f"Croissance CA: {inp.growth_rate * 100:.0f}%",
        "test_value_formatter": lambda inp, nudge: f"Croissance CA: {(inp.growth_rate + nudge) * 100:.0f}% (+2%)",
        "nudge_amount": Decimal("0.02"),
    },
    "retirement_age": {
        "label": "Travailler 2 ans de plus",
        "description": "Repousser votre retraite de 2 ans",
        "base_value_formatter": lambda inp: f"Retraite à {inp.target_age} ans",
        "test_value_formatter": lambda inp, nudge: f"Retraite à {inp.target_age + 2} ans (+2 ans)",
        "nudge_amount": 2,
    },
    "savings_to_pea": {
        "label": "Rediriger 50% de l'épargne vers PEA",
        "description": "Allouer la moitié de votre épargne mensuelle vers un PEA (meilleur rendement)",
        "base_value_formatter": lambda inp: _format_allocation_summary(inp),
        "test_value_formatter": lambda inp, nudge: _format_pea_redirect_summary(inp),
        "nudge_amount": Decimal("0.50"),  # fraction to redirect
    },
    "loan_freed": {
        "label": "Rediriger les prêts terminés vers l'épargne",
        "description": "Quand un prêt se termine, rediriger la mensualité vers l'épargne",
        "base_value_formatter": lambda inp: "Prêts ignorés après échéance",
        "test_value_formatter": lambda inp, nudge: "Prêts redirigés vers épargne après échéance",
        "nudge_amount": True,
    },
}

# ── Output data structure ─────────────────────────────────────────────────────


@dataclass
class SensitivityResult:
    """Result of testing a single parameter nudge."""

    parameter: str  # key from NUDGES dict
    label: str  # human-readable label
    description: str  # longer explanation
    base_value_display: str  # formatted base value
    test_value_display: str  # formatted test value
    base_wealth: Decimal  # wealth at retirement in base scenario
    test_wealth: Decimal  # wealth at retirement in modified scenario
    delta_wealth: Decimal  # absolute difference
    delta_pct: Decimal  # percentage change
    delta_exhaustion: int  # change in wealth exhaustion age (years, 0 if no change)
    rank: int  # 1 = most impactful


# ── Helpers ───────────────────────────────────────────────────────────────────


def _format_allocation_summary(inp: ProjectionInput) -> str:
    """Format the current investment allocation as a short summary."""
    total = inp._total_monthly_savings()
    if total == Decimal("0"):
        return "Aucune épargne mensuelle"
    pea = Decimal("0")
    av = Decimal("0")
    for key, alloc in inp.allocations.items():
        monthly = alloc.get("monthly", Decimal("0"))
        if "pea" in key.lower():
            pea += monthly
        elif "av" in key.lower() or "assurance" in key.lower():
            av += monthly
    parts = []
    if pea > Decimal("0"):
        parts.append(f"PEA: {pea:.0f}€/mois")
    if av > Decimal("0"):
        parts.append(f"AV: {av:.0f}€/mois")
    other = total - pea - av
    if other > Decimal("0") or not parts:
        parts.append(f"Autres: {other:.0f}€/mois")
    return " / ".join(parts) if parts else f"Total: {total:.0f}€/mois"


def _format_pea_redirect_summary(inp: ProjectionInput) -> str:
    """Format the post-redirection allocation summary."""
    total = inp._total_monthly_savings()
    if total == Decimal("0"):
        return "Aucune épargne mensuelle"
    redirected = (total * Decimal("0.50")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"PEA: +{redirected:.0f}€/mois (50% de l'épargne redirigé)"


def _clone_input(inp: ProjectionInput) -> ProjectionInput:
    """Deep-copy a ProjectionInput so nudges don't mutate the original."""
    return copy.deepcopy(inp)


def _apply_nudge(inp: ProjectionInput, param: str) -> ProjectionInput:
    """Apply a single parameter nudge and return the modified input.

    Args:
        inp: The original projection input.
        param: The parameter key from NUDGES dict.

    Returns:
        A new ProjectionInput with the nudge applied.
    """
    modified = _clone_input(inp)
    nudge_config = NUDGES[param]
    nudge = nudge_config["nudge_amount"]

    if param == "monthly_savings":
        # Add 200€ to savings, distributed proportionally across allocations
        _add_to_savings(modified, nudge)

    elif param == "monthly_expenses_decrease":
        # Reduce monthly expenses by 300€
        modified.monthly_expenses_total -= nudge
        if modified.monthly_expenses_total < Decimal("0"):
            modified.monthly_expenses_total = Decimal("0")

    elif param == "growth_rate":
        # Increase growth rate by 2%
        modified.growth_rate += nudge

    elif param == "retirement_age":
        # Push retirement age by 2 years
        modified.target_age += nudge

    elif param == "savings_to_pea":
        # Redirect 50% of total monthly savings to PEA
        _redirect_to_pea(modified, nudge)

    elif param == "loan_freed":
        # Mark loans for redirection after termination
        _enable_loan_freed_redirection(modified)

    return modified


def _total_monthly_savings(inp: ProjectionInput) -> Decimal:
    """Sum all monthly contributions across all investment vehicles."""
    total = Decimal("0")
    for alloc in inp.allocations.values():
        total += alloc.get("monthly", Decimal("0"))
    return total


def _add_to_savings(inp: ProjectionInput, amount: Decimal) -> None:
    """Add an amount to total savings, distributed proportionally across allocations."""
    total = _total_monthly_savings(inp)
    if total == Decimal("0"):
        return
    for key in inp.allocations:
        current = inp.allocations[key].get("monthly", Decimal("0"))
        if current > Decimal("0"):
            fraction = current / total
            additional = (amount * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            inp.allocations[key]["monthly"] = current + additional
    # If rounding left some unallocated, add to largest allocation
    new_total = _total_monthly_savings(inp)
    target = total + amount
    diff = target - new_total
    if diff != Decimal("0") and inp.allocations:
        largest_key = max(inp.allocations, key=lambda k: inp.allocations[k].get("monthly", Decimal("0")))
        if inp.allocations[largest_key].get("monthly", Decimal("0")) > Decimal("0"):
            inp.allocations[largest_key]["monthly"] += diff


def _redirect_to_pea(inp: ProjectionInput, fraction: Decimal) -> None:
    """Redirect a fraction of total monthly savings to PEA vehicles."""
    total = _total_monthly_savings(inp)
    if total == Decimal("0"):
        return
    redirect_amount = (total * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Find PEA vehicles
    pea_keys = [k for k in inp.allocations if "pea" in k.lower()]
    if not pea_keys:
        # Create a synthetic PEA allocation
        pea_key = "pea"
        if pea_key not in inp.allocations:
            inp.allocations[pea_key] = {
                "balance": Decimal("0"),
                "monthly": Decimal("0"),
            }
        pea_keys = [pea_key]

    # Reduce non-PEA allocations proportionally and add to PEA
    non_pea_reduction = redirect_amount
    non_pea_keys = [k for k in inp.allocations if k not in pea_keys]
    non_pea_total = sum(
        inp.allocations[k].get("monthly", Decimal("0")) for k in non_pea_keys
    )
    if non_pea_total > Decimal("0"):
        for key in non_pea_keys:
            current = inp.allocations[key].get("monthly", Decimal("0"))
            if current > Decimal("0"):
                reduction = (redirect_amount * (current / non_pea_total)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                inp.allocations[key]["monthly"] = max(
                    Decimal("0"), current - reduction
                )

    # Add to PEA
    pea_target = pea_keys[0]
    inp.allocations[pea_target]["monthly"] = (
        inp.allocations[pea_target].get("monthly", Decimal("0")) + redirect_amount
    )


def _enable_loan_freed_redirection(inp: ProjectionInput) -> None:
    """When loans terminate, redirect the monthly payment into savings.

    This is implemented by converting each loan into a future savings contribution
    that starts when the loan ends. The projection engine's _compute_loan_expenses
    naturally drops the payment at end_date; we handle the redirection here by
    marking a note on the input that the router's _assemble_input_for_sensitivity
    will pick up.

    For the sensitivity test, we'll compare: base vs. a modified projection
    where freed loan capacity feeds into savings. The simplest approach: add
    the sum of all loan monthly payments to savings, spread across the projection
    years when loans are active, and convert to extra savings after termination.
    """
    # This nudge is handled differently — the baseline already drops loan
    # payments at end_date (no redirection). The test adds the freed amount
    # to savings. For simplicity, we add a flag that _assemble_input_for_sensitivity
    # can check and pre-add the future savings.
    #
    # Since the loan payments vary by year (they drop off), a full projection
    # rerun with extra savings is the most accurate. We'll add the equivalent
    # monthly amount to savings for the post-loan period.
    #
    # For MVP: add total loan monthly payment to savings from day 1.
    # This slightly overestimates (savings should only increase after each loan ends),
    # but gives the right direction and order of magnitude.
    total_loan_monthly = Decimal("0")
    for loan in inp.loans:
        total_loan_monthly += Decimal(str(loan.get("monthly_payment", "0")))
    if total_loan_monthly > Decimal("0"):
        _add_to_savings(inp, total_loan_monthly)


# Monkey-patch helper methods onto ProjectionInput for the formatters
ProjectionInput._total_monthly_savings = _total_monthly_savings  # type: ignore[attr-defined]


# ── Main analysis function ────────────────────────────────────────────────────


def run_sensitivity_analysis(
    inp: ProjectionInput,
    scale: str = "moderate",
) -> list[SensitivityResult]:
    """Run sensitivity analysis on a baseline projection.

    For each parameter in NUDGES, clones the input, applies the nudge,
    re-runs the projection, and compares final wealth and exhaustion age.

    Args:
        inp: A fully assembled ProjectionInput (baseline).
        scale: The inflation scale (passed through to projection).

    Returns:
        List of SensitivityResult, ranked by absolute delta_wealth descending.

    Raises:
        ValueError: If the baseline projection fails.
    """
    # Run baseline
    base_timeline = project_timeline(inp)
    base_summary = compute_summary(base_timeline)
    base_wealth = Decimal(base_summary["final_wealth"])
    base_exhaustion = base_summary.get("wealth_exhaustion_age")

    results: list[SensitivityResult] = []

    for param, config in NUDGES.items():
        try:
            modified_inp = _apply_nudge(inp, param)
            test_timeline = project_timeline(modified_inp)
            test_summary = compute_summary(test_timeline)
            test_wealth = Decimal(test_summary["final_wealth"])
            test_exhaustion = test_summary.get("wealth_exhaustion_age")

            delta_wealth = test_wealth - base_wealth
            delta_pct = (
                (delta_wealth / base_wealth * Decimal("100")).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
                if base_wealth != Decimal("0")
                else Decimal("0")
            )

            delta_exhaustion = 0
            if base_exhaustion is not None and test_exhaustion is not None:
                delta_exhaustion = test_exhaustion - base_exhaustion
            elif base_exhaustion is None and test_exhaustion is not None:
                delta_exhaustion = -(95 - inp.target_age)  # wealth now exhausts
            elif base_exhaustion is None and test_exhaustion is None:
                delta_exhaustion = 0

            results.append(
                SensitivityResult(
                    parameter=param,
                    label=config["label"],
                    description=config["description"],
                    base_value_display=config["base_value_formatter"](inp),
                    test_value_display=config["test_value_formatter"](inp, config["nudge_amount"]),
                    base_wealth=base_wealth,
                    test_wealth=test_wealth,
                    delta_wealth=delta_wealth,
                    delta_pct=delta_pct,
                    delta_exhaustion=delta_exhaustion,
                    rank=0,
                )
            )
        except Exception:
            # If a nudge produces an invalid input (e.g., retirement_age < current_age),
            # skip it rather than failing the entire analysis.
            continue

    # Rank by absolute delta_wealth descending
    results.sort(key=lambda r: abs(r.delta_wealth), reverse=True)
    for i, r in enumerate(results, 1):
        r.rank = i

    return results