"""Retirement drawdown strategy — tax-optimal vehicle withdrawal order.

After retirement, the user draws income from investments rather than working.
Different vehicles have different tax treatments on withdrawal:
  - Livret A/LDDS: no tax, instant access (liquidity buffer)
  - PEA (held 5+ years): 17.2% PS on gains only
  - AV (held 8+ years): 17.2% PS on gains above 4,600€ abattement (single) / 9,200€ (couple)
  - AV (held < 8 years): 30% PFU on gains
  - PER: contributions taxed as income (IR), gains taxed at PFU

Strategy: maintain 6 months expenses in Livret A, then draw from PEA first
(best tax treatment), then AV, then PER (worst — taxed as income).

TASK-7.13: Replaces the simple 4% rule with tax-optimized withdrawal sequencing.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


# Vehicle withdrawal priority (best tax treatment first)
DRAWDOWN_ORDER = [
    "pea",        # 17.2% PS only after 5 years
    "av_uc",      # 17.2% PS + abattement after 8 years
    "av_euro",    # Same as above
    "scpi",       # 30% PFU (or IR for revenus fonciers)
    "per",        # IR on contributions + PFU on gains (worst)
]

LIQUIDITY_BUFFER_MONTHS = 6  # Keep 6 months expenses in Livret A/LDDS


def compute_drawdown_for_year(
    balances: dict[str, Decimal],
    monthly_need: Decimal,
    monthly_expenses: Decimal,
    tax_parts: Decimal = Decimal("1"),
    is_couple: bool = False,
) -> dict[str, Any]:
    """Compute one year of retirement drawdown.

    Args:
        balances: current balance per vehicle {vehicle_key: Decimal}
        monthly_need: target monthly income needed
        monthly_expenses: for liquidity buffer calculation
        tax_parts: for PER IR calculation (unused in simplified model)
        is_couple: affects AV abattement (4600 single, 9200 couple)

    Returns:
        {
            "withdrawals": {vehicle: amount_withdrawn},
            "taxes_paid": {vehicle: tax_on_withdrawal},
            "total_withdrawn": str,
            "total_tax": str,
            "net_income_monthly": actual monthly income after tax,
            "remaining_balances": {vehicle: new_balance},
            "liquidity_ok": bool,
            "strategy_notes": [str],
        }
    """
    annual_need = monthly_need * Decimal("12")
    withdrawals: dict[str, Decimal] = {}
    taxes: dict[str, Decimal] = {}
    notes: list[str] = []
    remaining = dict(balances)

    # Step 1: Ensure liquidity buffer in Livret A / LDDS
    buffer_target = monthly_expenses * Decimal(str(LIQUIDITY_BUFFER_MONTHS))
    livret_balance = remaining.get("livret_a", Decimal("0")) + remaining.get("ldds", Decimal("0"))

    liquidity_ok = livret_balance >= buffer_target
    if not liquidity_ok and livret_balance > 0:
        notes.append(
            f"Livret A sous le seuil de sécurité "
            f"({livret_balance:.0f}€ vs {buffer_target:.0f}€ cible)"
        )

    # Step 2: Draw from vehicles in priority order
    still_needed = annual_need
    for vehicle in DRAWDOWN_ORDER:
        if still_needed <= Decimal("0"):
            break
        bal = remaining.get(vehicle, Decimal("0"))
        if bal <= Decimal("0"):
            continue

        # How much to draw from this vehicle (gross up for tax)
        draw = min(bal, still_needed * _gross_up_factor(vehicle, is_couple))
        tax = _compute_withdrawal_tax(vehicle, draw, is_couple)
        net = draw - tax

        withdrawals[vehicle] = draw
        taxes[vehicle] = tax
        remaining[vehicle] = bal - draw
        still_needed -= net

    # Step 3: If still needed, draw from liquidity (Livret A, LDDS)
    if still_needed > Decimal("0"):
        for liq in ["livret_a", "ldds"]:
            bal = remaining.get(liq, Decimal("0"))
            if bal > Decimal("0") and still_needed > Decimal("0"):
                draw = min(bal, still_needed)
                withdrawals[liq] = draw
                taxes[liq] = Decimal("0")  # No tax on Livret A
                remaining[liq] = bal - draw
                still_needed -= draw

    total_withdrawn = sum(withdrawals.values(), Decimal("0"))
    total_tax = sum(taxes.values(), Decimal("0"))
    net_annual = total_withdrawn - total_tax

    return {
        "withdrawals": {
            k: str(v.quantize(Decimal("0.01")))
            for k, v in withdrawals.items()
        },
        "taxes_paid": {
            k: str(v.quantize(Decimal("0.01")))
            for k, v in taxes.items()
        },
        "total_withdrawn": str(total_withdrawn.quantize(Decimal("0.01"))),
        "total_tax": str(total_tax.quantize(Decimal("0.01"))),
        "net_income_monthly": str(
            (net_annual / Decimal("12")).quantize(Decimal("0.01"))
        ),
        "remaining_balances": {
            k: str(v.quantize(Decimal("0.01")))
            for k, v in remaining.items()
        },
        "liquidity_ok": liquidity_ok,
        "strategy_notes": notes,
    }


def _compute_withdrawal_tax(
    vehicle: str, amount: Decimal, is_couple: bool,
) -> Decimal:
    """Simplified tax on withdrawal. Assumes gains = 50% of withdrawal.

    The 50% gains ratio is a simplification — in reality, the proportion
    of gains vs contributions varies by vehicle and holding period.
    """
    gains_ratio = Decimal("0.5")  # Assume half is gains, half is contributions
    gains = amount * gains_ratio

    if vehicle == "pea":
        # PS only (assumed held 5+ years)
        return gains * Decimal("0.172")
    elif vehicle in ("av_euro", "av_uc"):
        abattement = Decimal("9200") if is_couple else Decimal("4600")
        taxable_gains = max(Decimal("0"), gains - abattement)
        return taxable_gains * Decimal("0.172")
    elif vehicle == "scpi":
        return gains * Decimal("0.30")  # PFU
    elif vehicle == "per":
        # Contributions taxed as income + gains at PFU
        # Simplified: ~25% blended rate
        return amount * Decimal("0.25")
    return Decimal("0")


def _gross_up_factor(vehicle: str, is_couple: bool) -> Decimal:
    """How much to withdraw gross to get 1€ net (approximate).

    These factors account for the tax drag — withdrawing 1€ gross
    from a taxed vehicle yields less than 1€ net, so we need to
    withdraw slightly more to meet the spending need.
    """
    # Simplified — assume 50% gains ratio
    if vehicle == "pea":
        return Decimal("1.09")   # Need 1.09€ gross to get 1€ net
    elif vehicle in ("av_euro", "av_uc"):
        return Decimal("1.05")   # Better due to abattement
    elif vehicle == "per":
        return Decimal("1.33")   # Worst — 25% tax
    return Decimal("1.15")       # Default for unknown vehicles