# TASK-8.6 — Fix Assurance-Vie Abattement: €9,200 for Married Couples

## Problem
The drawdown and return-tax modules apply a €4,600/year abattement on AV gains
(after 8 years). Per Art. 125-0 A CGI, this is the single-person amount.
A **married couple or PACS** filing jointly gets **€9,200/year** combined abattement.

Since Richard and Caro file jointly, the abattement should be €9,200.

## SCOPE BOUNDARY — DO NOT
- DO NOT change PEA, PER, SCPI tax logic
- DO NOT change pre-8-year AV logic (PFU 30% applies, no abattement)
- DO NOT change the drawdown sequence order

---

## Implementation steps

### Step 1 — Add marital status to projection inputs

In `ProjectionInput` dataclass (or equivalent), ensure `marital_status: str` is present.
It should already exist or can be derived from `has_spouse` + `spouse.relationship_type`.

### Step 2 — Update AV abattement constant in `vehicles.py` or `drawdown.py`

```python
def get_av_abattement(marital_status: str) -> float:
    """Annual AV gain abattement after 8 years (Art. 125-0 A CGI)."""
    if marital_status in ("married", "pacs"):
        return 9_200.0
    return 4_600.0
```

### Step 3 — Use in return-tax calculation

In the yearly investment return tax computation for AV Euro and AV UC (after 8 years):

```python
av_abattement = get_av_abattement(inp.marital_status)
taxable_gains = max(0, av_gains - av_abattement)
tax = taxable_gains * 0.172  # PS only after 8 years
```

### Step 4 — Use in drawdown module

In `drawdown.py`, when computing after-tax withdrawal from AV:
```python
av_abattement = get_av_abattement(inp.marital_status)
```

---

## DONE WHEN
- [ ] `get_av_abattement("married")` returns 9200
- [ ] `get_av_abattement("single")` returns 4600
- [ ] Annual AV return tax calculation uses the correct abattement
- [ ] Drawdown module uses the correct abattement
- [ ] Unit test: married couple with €10,000 AV gains → tax on €800 at 17.2% (not €5,400)

---
---

# TASK-8.7 — Fix Income Growth Rate: Null → Preset Fallback + AE CA Ceiling Warning

## Problem A — Null growth rates
All income sources have `annual_growth_rate = null`. The engine doc says it falls back
to the "global growth_rate for AE sources." In practice, it's unclear what rate is
actually being applied. Over 27 years, the difference between 0% and 2% growth is
the largest variable in the entire model.

## Problem B — No explicit income growth rates visible to user
The Revenue page shows income sources but not what growth rate applies to them.
The user cannot verify what the projection assumes.

## SCOPE BOUNDARY — DO NOT
- DO NOT change the projection engine's growth calculation formula
- DO NOT add per-source growth rate UI in this task (that's a future enhancement)
- DO NOT change income sources that are `is_active=false`

---

## Implementation steps

### Step 1 — Define scale-based income growth rates in constants

In `calculations/constants.py`, add:
```python
# Income growth rates per scale (nominal, i.e. not inflation-adjusted)
# AE freelance income grows faster than inflation in good years
INCOME_GROWTH_RATES = {
    "optimistic":  0.04,   # 4% nominal — strong revenue growth
    "moderate":    0.02,   # 2% nominal — matches inflation roughly
    "pessimistic": 0.00,   # 0% — flat income in nominal terms
}

# Salary growth rates per scale (separate from AE — salaries grow differently)
SALARY_GROWTH_RATES = {
    "optimistic":  0.03,
    "moderate":    0.015,
    "pessimistic": 0.00,
}
```

### Step 2 — Fix fallback logic in `_compute_accumulation_year()`

```python
# For each AE income source without an explicit annual_growth_rate:
for source in ae_sources:
    per_source_rate = source.annual_growth_rate
    if per_source_rate is None:
        # Fall back to scale-based preset
        per_source_rate = INCOME_GROWTH_RATES[inp.growth_scale]
    
    years_active = max(0, year_offset - source_start_offset)
    source_income = source.monthly_amount * 12 * (1 + per_source_rate) ** years_active

# For salary sources:
for source in salary_sources:
    per_source_rate = source.annual_growth_rate
    if per_source_rate is None:
        per_source_rate = SALARY_GROWTH_RATES[inp.growth_scale]
    ...
```

### Step 3 — Add "effective growth rate" annotation to Revenue page

On `frontend/src/routes/(app)/revenue/+page.svelte`, next to each income source row,
show a small badge:

```svelte
<span class="growth-badge">
  +{(source.annual_growth_rate ?? defaultGrowthRate) * 100}%/an
</span>
```

Where `defaultGrowthRate` comes from the profile's growth_scale setting.
Add a tooltip: "Taux de croissance annuel appliqué à ce revenu dans vos projections."

### Step 4 — AE CA ceiling projection warning on Revenue page

After fetching the projection data, check for `ae_ceiling_breach` years (from TASK-8.3)
and display a banner on the Revenue page:

```svelte
{#if projectionData?.ae_ceiling_breach_year}
  <div class="banner warning">
    ⚠️ À ce rythme, votre CA dépassera le plafond micro-BNC (83 600 €) 
    en {projectionData.ae_ceiling_breach_year}. Vous devrez alors basculer 
    vers un autre régime juridique (SASU, EURL ou EI au réel).
  </div>
{/if}
```

---

## DONE WHEN (8.7)
- [ ] `INCOME_GROWTH_RATES` and `SALARY_GROWTH_RATES` are defined in constants.py per scale
- [ ] Null `annual_growth_rate` sources correctly fall back to scale rate (not 0%)
- [ ] Revenue page shows effective growth rate badge per source
- [ ] Revenue page shows AE CA ceiling warning when breach is projected
- [ ] At moderate scale: AE sources grow at 2%/yr, salary sources at 1.5%/yr
- [ ] Unit test: null growth_rate source at moderate scale → same result as explicit 0.02
