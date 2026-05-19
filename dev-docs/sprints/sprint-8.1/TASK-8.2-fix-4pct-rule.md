# TASK-8.2 — Fix 4% Passive Income Rule: Investments Only, Not Primary Residence

## Problem
`passive_monthly = total_wealth × 4% / 12` where `total_wealth` currently includes
`property_primary_value`. A primary residence generates no income — applying the 4%
rule to it overstates passive income by `320,000 × 4% / 12 = €1,067/month` today,
growing with property appreciation to ~€1,818/month by retirement (at 2%/yr × 27 years).

This inflates the readiness score, the "patrimoine à 67 ans" passive income stat,
and the goal-reached detection. It is the second-most impactful bug after tax parts.

## SCOPE BOUNDARY — DO NOT
- DO NOT remove property from the net worth total (property is correctly part of total net worth)
- DO NOT change the property appreciation calculation
- DO NOT change the drawdown module
- DO NOT modify the net_worth_snapshots schema

---

## Root cause
In `backend/app/calculations/projection.py`, the derived values block computes:
```python
wealth = sum(vehicle_balances) + property_value   # ← correct for net worth
passive_monthly = wealth * 0.04 / 12              # ← WRONG: uses total incl. property
```

---

## Implementation steps

### Step 1 — Split liquid wealth from total wealth in projection output

In `_compute_accumulation_year()` and `_compute_retirement_year()`, add a new field:

```python
liquid_wealth = sum(vehicle_balances)   # investments only
total_wealth = liquid_wealth + property_value   # for net worth display
passive_monthly = liquid_wealth * 0.04 / 12     # FIX: investments only
```

Both `liquid_wealth` and `total_wealth` are passed through to the response.

### Step 2 — Update compute_summary()

```python
# Currently: final_wealth = peak total_wealth (incl. property)
# Change to two fields:
summary["final_liquid_wealth"] = peak liquid_wealth
summary["final_total_wealth"] = peak total_wealth (liquid + property)
summary["final_passive_monthly"] = peak liquid_wealth * 0.04 / 12
```

### Step 3 — Update frontend display

In the runway page hero stats:
- "Patrimoine à 67 ans" card: display `final_total_wealth` (keep showing total net worth — this is correct)
- "Revenu passif mensuel" card: use `final_passive_monthly` (now liquid only — this fixes the bug)
- Add a small legend under the patrimoine card: "dont {fmtK(final_liquid_wealth)} en épargne liquide"

### Step 4 — Update readiness score

In `readiness.py`, the goal_coverage component uses `retirement_monthly_income` which
includes `passive_monthly`. Because passive_monthly is now corrected, goal_coverage
will automatically be recalculated correctly. No other change needed.

### Step 5 — Update the retirement monthly income formula

Currently:
```python
retirement_monthly_income = passive_monthly + (project_income + pension) / 12
```
This stays the same — but `passive_monthly` is now correct (liquid only).

---

## DONE WHEN
- [ ] `liquid_wealth` and `total_wealth` are separate fields in each YearResult
- [ ] `passive_monthly` = `liquid_wealth × 4% / 12` in all year calculations
- [ ] `final_passive_monthly` in summary uses liquid wealth
- [ ] Hero stat "Revenu passif mensuel" uses the corrected value
- [ ] Hero stat "Patrimoine" still shows total wealth (liquid + property)
- [ ] Subtitle added: "dont Xk€ en épargne liquide / Xk€ en immobilier"
- [ ] Unit test: with 0 investments + 320k property → passive_monthly = 0, total_wealth = 320k
