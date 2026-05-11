# TASK-7.8: Couple-Aware Projection Engine

**Status:** TODO
**Sprint:** 7
**Priority:** P2 (medium — integration task)
**Est. effort:** 3 hr
**Dependencies:** TASK-7.4, TASK-7.5, TASK-7.7

---

## Context

The projection engine currently models one income stream, one set of cotisations, one pension. This task integrates spouse income, income source timelines (replacing flat CA growth), and dual pensions into the 30-year projection. When no spouse or income sources exist, behavior is unchanged.

---

## Step-by-Step Instructions

### Step 1: Extend ProjectionInput

File: `backend/app/calculations/projection.py`

Add fields to the `ProjectionInput` dataclass:

```python
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
# Each: {earner, label, amount, frequency, start_date, end_date, growth_rate, is_ae_revenue}
# If None → use monthly_gross_ca with growth_rate (backward compat)
```

### Step 2: Income source timeline computation

Add a helper function:

```python
def compute_income_for_year(
    sources: list[dict],
    year: int,
    earner: str,
    ae_only: bool = False,
) -> Decimal:
    """Sum active income sources for a given year and earner.
    
    Args:
        sources: list of income source dicts
        year: the projection year
        earner: "user" or "spouse"
        ae_only: if True, only include is_ae_revenue=True sources
    
    Returns:
        Annual income from matching sources
    """
    total = Decimal("0")
    for src in sources:
        if src["earner"] != earner:
            continue
        if ae_only and not src.get("is_ae_revenue", True):
            continue
        
        # Check if source is active this year
        start_year = int(src["start_date"][:4]) if src.get("start_date") else 0
        end_year = int(src["end_date"][:4]) if src.get("end_date") else 9999
        if year < start_year or year > end_year:
            continue
        
        # Skip one-time sources (handled separately)
        if src["frequency"] == "one_time":
            continue
        
        amount = Decimal(str(src["amount"]))
        # Apply growth from source start
        growth = Decimal(str(src.get("annual_growth_rate") or "0"))
        years_active = max(0, year - max(start_year, 2026))
        grown = amount * (1 + growth) ** years_active
        
        if src["frequency"] == "monthly":
            total += grown * 12
        elif src["frequency"] == "annual":
            total += grown
    
    return total


def compute_onetime_income_for_year(sources: list[dict], year: int) -> Decimal:
    """Sum one-time income events in a given year."""
    total = Decimal("0")
    for src in sources:
        if src["frequency"] != "one_time":
            continue
        if src.get("start_date") and int(src["start_date"][:4]) == year:
            total += Decimal(str(src["amount"]))
    return total
```

### Step 3: Update the year loop in project_timeline()

Inside the main `for year in range(start_year, end_year + 1):` loop:

**Replace the single CA computation:**

```python
# OLD:
# gross = inp.monthly_gross_ca * 12 * (1 + inp.growth_rate) ** (year - start_year)

# NEW:
if inp.income_sources:
    user_ae_income = compute_income_for_year(inp.income_sources, year, "user", ae_only=True)
    user_non_ae_income = compute_income_for_year(inp.income_sources, year, "user", ae_only=False) - user_ae_income
    spouse_income = compute_income_for_year(inp.income_sources, year, "spouse")
    onetime = compute_onetime_income_for_year(inp.income_sources, year)
    gross = user_ae_income  # AE cotisations apply to this
else:
    # Backward compat
    gross = inp.monthly_gross_ca * 12 * (1 + inp.growth_rate) ** (year - start_year)
    user_non_ae_income = Decimal("0")
    spouse_income = Decimal("0")
    onetime = Decimal("0")
```

**Add spouse income and cotisations:**

```python
# Spouse cotisations (simplified)
spouse_age = (inp.spouse_retirement_age or inp.target_age) - (inp.target_age - age)
spouse_retired = spouse_age >= (inp.spouse_retirement_age or inp.target_age)

if spouse_retired:
    spouse_annual = inp.spouse_pension_monthly * 12
    spouse_charges = Decimal("0")
else:
    if inp.income_sources:
        spouse_annual = spouse_income
    else:
        spouse_annual = inp.spouse_monthly_gross * 12 * (1 + inp.spouse_growth_rate) ** (year - start_year)
    # Spouse cotisations depend on status
    if inp.spouse_ae_type:
        spouse_rate = get_ae_rate(inp.spouse_ae_type, year)
        spouse_charges = spouse_annual * spouse_rate
    else:
        spouse_charges = spouse_annual * Decimal("0.23")  # Simplified salaried rate
```

**CC cotisation as expense:**
```python
cc_expense = inp.cc_annual_cotisation if not spouse_retired else Decimal("0")
```

**Update total_income and total_outgoing:**
```python
total_income = gross + user_non_ae_income + spouse_annual + onetime + proj_inc + caf + tax_credits + status_bonus
total_outgoing = charges + spouse_charges + cc_expense + cfe + base_exp + kid_exp + pet_exp + car_exp + tech_exp + rec_exp + proj_exp + loan_exp + year_invested
```

### Step 4: Update input assembly in the router

File: `backend/app/routers/projection.py` → `_assemble_input()`

Load spouse and income sources:

```python
# Load spouse
spouse = await db.execute(select(Spouse).where(Spouse.user_id == user_id))
spouse_data = spouse.scalar_one_or_none()

# Load income sources
sources_result = await db.execute(
    select(IncomeSource).where(IncomeSource.user_id == user_id, IncomeSource.is_active == True)
)
income_sources = [
    {
        "earner": s.earner,
        "label": s.label,
        "amount": str(s.amount),
        "frequency": s.frequency,
        "start_date": s.start_date.isoformat() if s.start_date else None,
        "end_date": s.end_date.isoformat() if s.end_date else None,
        "annual_growth_rate": str(s.annual_growth_rate) if s.annual_growth_rate else None,
        "is_ae_revenue": s.is_ae_revenue,
    }
    for s in sources_result.scalars().all()
]

# Add to ProjectionInput
inp.income_sources = income_sources if income_sources else None
if spouse_data:
    inp.spouse_monthly_gross = spouse_data.monthly_gross_income or Decimal("0")
    inp.spouse_ae_type = spouse_data.ae_activity_type
    # ... load spouse pension from pension endpoint
    if spouse_data.is_conjointe_collaboratrice and spouse_data.cc_cotisation_option:
        inp.cc_annual_cotisation = estimate_cc_annual(spouse_data.cc_cotisation_option, profile.monthly_gross_ca * 12)
```

### Step 5: Update sensitivity analysis

File: `backend/app/calculations/sensitivity.py`

Add two new nudge parameters:

```python
"spouse_income_increase": {
    "label": "Augmenter le revenu conjoint de 500€/mois",
    "description": "Le conjoint gagne 500€/mois de plus",
    "nudge_amount": Decimal("500"),
},
```

Only include this nudge if a spouse exists (check `inp.spouse_monthly_gross > 0`).

### Step 6: Unit tests

Add to `backend/tests/test_projection.py`:

**Scenario C — Couple, no income sources:**
User CA 5000€/mois, spouse salary 2800€/mois CDI, 3 kids, verify household income and dual retirement.

**Scenario D — Income sources:**
User with 3 sources (one ending in 2028), verify income drops in 2029, one-time sale in 2030 appears.

---

## SCOPE BOUNDARY

- DO NOT add UI changes. This is engine-only.
- DO NOT model spouse investments separately — they share household savings.
- DO NOT implement the full IR tax model here — that's TASK-7.12.
- DO NOT model spouse retirement independently if the ages differ by more than 5 years — use the user's target age as a proxy for both unless `spouse_retirement_age` is explicitly set.
- Spouse cotisation rate for CDI (23%) is a simplification. DO NOT model the exact salarial/patronal breakdown.
- Expected change: ~100 lines in projection.py, ~40 lines in router, ~20 lines in sensitivity.

## DONE WHEN

- [ ] Projection produces household income when spouse exists
- [ ] Income source timeline replaces flat CA growth when sources exist
- [ ] One-time income events appear in the correct year
- [ ] CC cotisations deducted as expense during working years
- [ ] Dual pension after retirement
- [ ] Sensitivity includes spouse parameter when applicable
- [ ] Single-person mode unchanged (backward compat)
- [ ] Scenarios C and D pass
