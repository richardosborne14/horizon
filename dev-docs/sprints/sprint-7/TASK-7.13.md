# TASK-7.13: Retirement Drawdown Strategy

**Status:** TODO
**Sprint:** 7
**Priority:** P2 (medium)
**Est. effort:** 2.5 hr
**Dependencies:** TASK-4.1

---

## Context

The projection currently uses a blanket "4% rule" for passive income: `wealth × 0.04 / 12`. In reality, retirees draw from different vehicles in a tax-optimal order: PEA first (tax-free after 5 years), then AV (favorable after 8 years with abattement), Livret A as liquidity buffer, PER taxed as income on exit. The ORDER of drawdown matters for both tax efficiency and how long wealth lasts.

---

## Step-by-Step Instructions

### Step 1: Create drawdown strategy module

Create `backend/app/calculations/drawdown.py`:

```python
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
        tax_parts: for PER IR calculation
        is_couple: affects AV abattement (4600 single, 9200 couple)

    Returns:
        {
            "withdrawals": {vehicle: amount_withdrawn},
            "taxes_paid": {vehicle: tax_on_withdrawal},
            "net_income_monthly": actual monthly income after tax,
            "remaining_balances": {vehicle: new_balance},
            "liquidity_ok": bool,
            "strategy_notes": [str],
        }
    """
    annual_need = monthly_need * 12
    withdrawals: dict[str, Decimal] = {}
    taxes: dict[str, Decimal] = {}
    notes: list[str] = []
    remaining = dict(balances)

    # Step 1: Ensure liquidity buffer in Livret A / LDDS
    buffer_target = monthly_expenses * LIQUIDITY_BUFFER_MONTHS
    livret_balance = remaining.get("livret_a", Decimal("0")) + remaining.get("ldds", Decimal("0"))
    if livret_balance < buffer_target:
        notes.append(f"Livret A sous le seuil de sécurité ({livret_balance:.0f}€ vs {buffer_target:.0f}€ cible)")

    # Step 2: Draw from vehicles in priority order
    still_needed = annual_need
    for vehicle in DRAWDOWN_ORDER:
        if still_needed <= 0:
            break
        bal = remaining.get(vehicle, Decimal("0"))
        if bal <= 0:
            continue

        # How much to draw from this vehicle
        draw = min(bal, still_needed * _gross_up_factor(vehicle, is_couple))
        tax = _compute_withdrawal_tax(vehicle, draw, is_couple)
        net = draw - tax

        withdrawals[vehicle] = draw
        taxes[vehicle] = tax
        remaining[vehicle] = bal - draw
        still_needed -= net

    # Step 3: If still needed, draw from liquidity (Livret A)
    if still_needed > 0:
        for liq in ["livret_a", "ldds"]:
            bal = remaining.get(liq, Decimal("0"))
            if bal > 0 and still_needed > 0:
                draw = min(bal, still_needed)
                withdrawals[liq] = draw
                taxes[liq] = Decimal("0")  # No tax on Livret A
                remaining[liq] = bal - draw
                still_needed -= draw

    total_withdrawn = sum(withdrawals.values())
    total_tax = sum(taxes.values())
    net_annual = total_withdrawn - total_tax
    
    return {
        "withdrawals": {k: str(v.quantize(Decimal("0.01"))) for k, v in withdrawals.items()},
        "taxes_paid": {k: str(v.quantize(Decimal("0.01"))) for k, v in taxes.items()},
        "total_withdrawn": str(total_withdrawn.quantize(Decimal("0.01"))),
        "total_tax": str(total_tax.quantize(Decimal("0.01"))),
        "net_income_monthly": str((net_annual / 12).quantize(Decimal("0.01"))),
        "remaining_balances": {k: str(v.quantize(Decimal("0.01"))) for k, v in remaining.items()},
        "liquidity_ok": livret_balance >= buffer_target,
        "strategy_notes": notes,
    }


def _compute_withdrawal_tax(vehicle: str, amount: Decimal, is_couple: bool) -> Decimal:
    """Simplified tax on withdrawal. Assumes gains = 50% of withdrawal."""
    gains_ratio = Decimal("0.5")  # Assume half is gains, half is contributions
    gains = amount * gains_ratio

    if vehicle == "pea":
        return gains * Decimal("0.172")  # PS only (held 5+ years assumed)
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
    """How much to withdraw gross to get 1€ net."""
    # Simplified — assume 50% gains ratio
    if vehicle == "pea":
        return Decimal("1.09")   # Need 1.09€ gross to get 1€ net
    elif vehicle in ("av_euro", "av_uc"):
        return Decimal("1.05")   # Better due to abattement
    elif vehicle == "per":
        return Decimal("1.33")   # Worst — 25% tax
    return Decimal("1.15")       # Default
```

### Step 2: Integrate into projection engine

File: `backend/app/calculations/projection.py`

In the post-retirement years of the year loop, replace:

```python
# OLD:
passive = wealth * Decimal("0.04") / 12
```

With:

```python
# NEW:
if age >= inp.target_age:
    drawdown = compute_drawdown_for_year(
        balances=balances,
        monthly_need=inp.monthly_revenue_goal or (base_exp / 12),
        monthly_expenses=base_exp / 12,
        tax_parts=inp.tax_parts,
        is_couple=inp.spouse_monthly_gross > 0,
    )
    passive = Decimal(drawdown["net_income_monthly"])
    # Update balances from drawdown
    for vehicle, new_bal in drawdown["remaining_balances"].items():
        balances[vehicle] = Decimal(new_bal)
else:
    passive = wealth * Decimal("0.04") / 12
```

### Step 3: Drawdown info on Runway page

Add a small section below the projection table showing the drawdown strategy summary:

```svelte
{#if drawdownStrategy}
  <div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
    <p class="text-xs font-semibold text-zinc-300 mb-2">💰 Stratégie de décaissement</p>
    <p class="text-[10px] text-zinc-500 mb-2">
      Ordre de retrait optimisé fiscalement : PEA → AV → SCPI → PER
    </p>
    <div class="text-[10px] text-zinc-400 space-y-1">
      <p>Livret A maintenu comme réserve de sécurité ({LIQUIDITY_BUFFER_MONTHS} mois de dépenses)</p>
      {#each drawdownStrategy.notes as note}
        <p class="text-amber-400">⚠️ {note}</p>
      {/each}
    </div>
  </div>
{/if}
```

### Step 4: Unit tests

Create `backend/tests/test_drawdown.py`:
- Test drawdown from PEA first, then AV
- Test PER tax calculation (~25%)
- Test AV abattement (single vs couple)
- Test liquidity buffer warning
- Test empty vehicles (skip gracefully)

---

## SCOPE BOUNDARY

- DO NOT model exact gains vs contributions per vehicle. The 50% gains ratio is a simplification.
- DO NOT model partial-year drawdowns. This is annual.
- DO NOT add a drawdown configuration UI. The strategy is automatic (tax-optimal order).
- DO NOT model social charges on PER withdrawal separately.
- Expected: ~100 lines drawdown module, ~15 lines engine integration, ~30 lines frontend.

## DONE WHEN

- [ ] Drawdown module computes tax-optimal withdrawal order
- [ ] PEA drawn first, PER last
- [ ] AV abattement applied correctly (single vs couple)
- [ ] Liquidity buffer maintained in Livret A
- [ ] Projection uses drawdown for post-retirement years
- [ ] Drawdown strategy summary shown on Runway page
- [ ] Tests pass
