# TASK-7.12: Simplified IR Tax Model

**Status:** TODO
**Sprint:** 7
**Priority:** P1 (high — biggest accuracy improvement)
**Est. effort:** 3 hr
**Dependencies:** None

---

## Context

The projection engine currently ignores income tax (IR). All "net" figures are pre-tax. For a couple with 3 kids (3.5 parts), IR changes the picture dramatically — their effective rate is much lower than a single person. Without IR, the retirement projection is systematically optimistic (it assumes you keep money you actually owe in tax).

This task adds a simplified IR model using the 2024 barème with quotient familial. It's a first approximation — not a full tax simulator.

---

## Step-by-Step Instructions

### Step 1: Create the IR calculation module

Create `backend/app/calculations/income_tax.py`:

```python
"""Simplified French income tax (IR) calculation.

Uses the 2024 barème progressif with quotient familial.
This is a first approximation:
- Does not model prélèvement à la source mechanics
- Does not model specific deductions beyond standard 10%
- Does not model micro-BIC/BNC abattement interaction with IR
- DOES model quotient familial correctly (divide by parts, apply barème, multiply back)
"""
from decimal import Decimal, ROUND_HALF_UP


# 2024 IR barème (tranches)
IR_TRANCHES_2024 = [
    (Decimal("11294"), Decimal("0")),        # 0% up to 11,294€
    (Decimal("28797"), Decimal("0.11")),      # 11% from 11,294 to 28,797€
    (Decimal("82341"), Decimal("0.30")),      # 30% from 28,797 to 82,341€
    (Decimal("177106"), Decimal("0.41")),     # 41% from 82,341 to 177,106€
    (None, Decimal("0.45")),                  # 45% above 177,106€
]

# AE micro-fiscal abattements
AE_ABATTEMENTS = {
    "bic_vente": Decimal("0.71"),     # 71% abattement
    "bic_service": Decimal("0.50"),   # 50%
    "bic_heberg": Decimal("0.50"),    # 50%
    "bnc": Decimal("0.34"),           # 34%
}

# Standard 10% deduction for salaries
SALARY_DEDUCTION_RATE = Decimal("0.10")
SALARY_DEDUCTION_MIN = Decimal("495")
SALARY_DEDUCTION_MAX = Decimal("14171")


def compute_ir(
    ae_ca_annual: Decimal,
    ae_activity_type: str,
    salary_annual: Decimal = Decimal("0"),
    other_income_annual: Decimal = Decimal("0"),
    tax_parts: Decimal = Decimal("1"),
    cesu_credit: Decimal = Decimal("0"),
    charity_reduction: Decimal = Decimal("0"),
    has_vl: bool = False,
) -> dict:
    """Compute annual IR for a household.
    
    Args:
        ae_ca_annual: Auto-entrepreneur CA brut annuel
        ae_activity_type: bic_vente, bic_service, bnc, bic_heberg
        salary_annual: Spouse salary brut annuel (if CDI)
        other_income_annual: Dividends, rental, etc. (already net of deductions)
        tax_parts: Quotient familial parts (1=seul, 2=couple, +0.5/enfant, +1 au 3ème)
        cesu_credit: CESU tax credit (50% of CESU, max 6000€)
        charity_reduction: Charity tax reduction (66% of dons)
        has_vl: If True, AE income is already taxed via versement libératoire → exclude from IR
    
    Returns:
        {
            "revenu_imposable": total taxable income,
            "ir_brut": IR before credits,
            "ir_net": IR after credits,
            "taux_effectif": effective rate as decimal,
            "taux_marginal": marginal rate as decimal,
            "monthly_ir": monthly IR amount,
        }
    """
    # Step 1: Compute revenu imposable
    
    # AE income: apply micro-fiscal abattement (unless VL)
    if has_vl:
        ae_taxable = Decimal("0")  # VL = already taxed at flat rate
    else:
        abattement = AE_ABATTEMENTS.get(ae_activity_type, Decimal("0.34"))
        ae_taxable = ae_ca_annual * (1 - abattement)
    
    # Salary income: 10% deduction
    salary_deduction = max(
        SALARY_DEDUCTION_MIN,
        min(salary_annual * SALARY_DEDUCTION_RATE, SALARY_DEDUCTION_MAX)
    ) if salary_annual > 0 else Decimal("0")
    salary_taxable = max(Decimal("0"), salary_annual - salary_deduction)
    
    # Total revenu imposable
    revenu_imposable = ae_taxable + salary_taxable + other_income_annual
    
    # Step 2: Apply quotient familial
    revenu_par_part = revenu_imposable / tax_parts
    
    # Step 3: Apply barème to revenu_par_part
    ir_par_part = _apply_bareme(revenu_par_part)
    
    # Step 4: Multiply back by parts
    ir_brut = ir_par_part * tax_parts
    
    # Step 5: Apply plafonnement du quotient familial
    # Simplified: max advantage per demi-part above 2 = 1,759€
    # For parts > 2: cap the advantage
    extra_half_parts = max(Decimal("0"), (tax_parts - 2) * 2)  # number of extra half-parts
    if extra_half_parts > 0:
        ir_sans_enfants = _apply_bareme(revenu_imposable / 2) * 2
        advantage = ir_sans_enfants - ir_brut
        max_advantage = extra_half_parts * Decimal("1759")
        if advantage > max_advantage:
            ir_brut = ir_sans_enfants - max_advantage
    
    # Step 6: Apply credits and reductions
    ir_net = max(Decimal("0"), ir_brut - cesu_credit - charity_reduction)
    
    # Effective and marginal rates
    taux_effectif = (ir_net / revenu_imposable).quantize(Decimal("0.0001")) if revenu_imposable > 0 else Decimal("0")
    taux_marginal = _marginal_rate(revenu_par_part)
    
    return {
        "revenu_imposable": str(revenu_imposable.quantize(Decimal("0.01"))),
        "ir_brut": str(ir_brut.quantize(Decimal("0.01"))),
        "ir_net": str(ir_net.quantize(Decimal("0.01"))),
        "taux_effectif": str(taux_effectif),
        "taux_marginal": str(taux_marginal),
        "monthly_ir": str((ir_net / 12).quantize(Decimal("0.01"))),
    }


def _apply_bareme(revenu_par_part: Decimal) -> Decimal:
    """Apply progressive barème to income per part."""
    ir = Decimal("0")
    prev_threshold = Decimal("0")
    
    for threshold, rate in IR_TRANCHES_2024:
        if threshold is None:
            ir += (revenu_par_part - prev_threshold) * rate
            break
        elif revenu_par_part <= threshold:
            ir += (revenu_par_part - prev_threshold) * rate
            break
        else:
            ir += (threshold - prev_threshold) * rate
            prev_threshold = threshold
    
    return ir


def _marginal_rate(revenu_par_part: Decimal) -> Decimal:
    """Return the marginal rate for the given income per part."""
    for threshold, rate in IR_TRANCHES_2024:
        if threshold is None or revenu_par_part <= threshold:
            return rate
    return Decimal("0.45")
```

### Step 2: Integrate into projection engine

File: `backend/app/calculations/projection.py`

Inside the year loop, after computing `total_income` and `total_outgoing`, compute IR:

```python
from app.calculations.income_tax import compute_ir

# Compute IR for this year
ir_result = compute_ir(
    ae_ca_annual=gross,
    ae_activity_type=inp.ae_activity_type,
    salary_annual=spouse_annual if not spouse_retired and not inp.spouse_ae_type else Decimal("0"),
    other_income_annual=user_non_ae_income + (spouse_annual if inp.spouse_ae_type else Decimal("0")),
    tax_parts=inp.tax_parts,
    cesu_credit=min(inp.cesu_annual * Decimal("0.5"), Decimal("6000")),
    charity_reduction=min(inp.charity_annual * Decimal("0.66"), Decimal("20000")),
    has_vl=inp.versement_liberatoire,
)
ir_annual = Decimal(ir_result["ir_net"])

# Add IR to outgoing
total_outgoing += ir_annual
```

### Step 3: Add IR to YearProjection dataclass

Add fields:
```python
ir_annual: Decimal = Decimal("0")
ir_monthly: Decimal = Decimal("0")
taux_effectif: Decimal = Decimal("0")
```

### Step 4: Frontend — show IR in stats and table

File: `frontend/src/routes/(app)/runway/+page.svelte`

Add IR column to the projection table (between "Net" and "Patrimoine"):
```
| IR/an | Net après IR |
```

Add IR stat card (rose) to the stats row.

### Step 5: IR preview on Revenue page

File: `frontend/src/routes/(app)/revenue/+page.svelte`

Add a small IR estimate card showing estimated annual and monthly IR based on current inputs. Fetch from a new endpoint or compute client-side using the barème.

### Step 6: Unit tests

Create `backend/tests/test_income_tax.py`:
- Test single person, AE BNC, 50k CA → verify IR matches hand calculation
- Test couple (2 parts), AE + CDI spouse, 3 kids (3.5 parts) → verify quotient familial works
- Test VL = true → AE income excluded from IR
- Test CESU credit reduces IR
- Test plafonnement du quotient familial

---

## SCOPE BOUNDARY

- DO NOT model prélèvement à la source withholding mechanics. This is annual IR only.
- DO NOT model micro-BIC/BNC option vs réel. Assume micro (abattement forfaitaire).
- DO NOT model specific deductions (frais réels, etc.) — only the standard 10%.
- DO NOT inflate the barème tranches over the projection. Use 2024 values for all years (simplification).
- DO NOT model CSG/CRDS deductibility. This is a first approximation.
- Expected: ~120 lines tax module, ~20 lines engine integration, ~30 lines frontend, ~60 lines tests.

## DONE WHEN

- [ ] `compute_ir()` returns correct IR for single and couple scenarios
- [ ] Quotient familial correctly divides, applies barème, multiplies back
- [ ] Plafonnement caps the advantage per half-part
- [ ] VL excludes AE income from IR
- [ ] CESU and charity credits reduce IR
- [ ] Projection table shows IR column
- [ ] Projection `net_annual` now reflects after-IR net
- [ ] Revenue page shows IR estimate
- [ ] All tests pass
