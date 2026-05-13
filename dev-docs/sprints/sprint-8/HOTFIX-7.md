# HOTFIX-7: Revenue Timeline Chart Does Not Reflect Income Growth

**Severity:** MEDIUM (visual bug — misleading chart, calculation may be unaffected)  
**Discovered:** 2026-05-12 via screenshot audit  
**Depends on:** HOTFIX-1 must be deployed first (fixes the underlying calculation)

## Problem

The "Timeline des revenus" bar chart on the Revenus page shows a flat **7,600€ for every year from 2026 to 2035**. The user has "Ambitieux 6%" growth selected. With 6% annual growth, the 2035 bar should show approximately **12,840€**, not 7,600€.

The chart appears to read base monthly amounts from `income_sources` directly (the same flat values that HOTFIX-1 fixes in the projection engine), rather than calling the projection engine's grown values. This means:
- The projection table (Horizon tab) will be correct after HOTFIX-1
- The timeline chart on the Revenus tab will still show flat bars
- The user sees contradictory information between two screens

Additionally, the conjoint salary line should be visually distinct in the chart. Currently the legend shows "Vous" (teal) and "Conjoint" (purple), but all bars appear to be one colour — suggesting the conjoint income may not be rendering as a separate segment.

---

## Root Cause

The timeline chart almost certainly fetches raw `income_sources` amounts and multiplies by 12 for each year, without applying the growth rate. After HOTFIX-1, the projection engine applies growth, but the chart has its own data-fetching logic that was not updated.

Two possible patterns:
- **Pattern A:** The chart calls a dedicated `/api/income-timeline` endpoint that returns flat base values → fix the endpoint to apply growth
- **Pattern B:** The chart computes values directly in the frontend from the income_sources store → fix the frontend computation to apply growth

---

## Fix

### Step 1 — Identify the chart data source

Find the "Timeline des revenus" component. Trace where it gets its data:
- Is there an API call? If so, find the endpoint.
- Is it computed from a Svelte store or prop? If so, find the computation.

### Step 2 — Apply growth rate to each year's values

Wherever the year-by-year income values are computed, apply the same growth logic as the projection engine:

```python
# Backend endpoint (if Pattern A):
def get_income_timeline(user_id: str, years: int = 10):
    sources = get_income_sources(user_id)
    growth_rate = get_growth_rate(user_id)  # e.g. 0.06 for "ambitieux"
    
    result = []
    for y in range(years):
        year = current_year + y
        # Apply growth only to AE sources (same rule as HOTFIX-1)
        user_income = sum(
            s.amount_monthly * 12 * (1 + growth_rate) ** y
            for s in sources if s.is_ae_revenue
        )
        # Non-AE (salary, conjoint) — flat, no growth
        non_ae_income = sum(
            s.amount_monthly * 12
            for s in sources if not s.is_ae_revenue
        )
        result.append({
            "year": year,
            "user_ae": user_income,
            "non_ae": non_ae_income,
            "total": user_income + non_ae_income
        })
    return result
```

```javascript
// Frontend computation (if Pattern B):
function computeTimeline(sources, growthRate, years = 10) {
  return Array.from({ length: years }, (_, y) => {
    const aeIncome = sources
      .filter(s => s.is_ae_revenue)
      .reduce((sum, s) => sum + s.amount_monthly * 12 * Math.pow(1 + growthRate, y), 0);
    const nonAeIncome = sources
      .filter(s => !s.is_ae_revenue)
      .reduce((sum, s) => sum + s.amount_monthly * 12, 0);
    return { year: currentYear + y, ae: aeIncome, nonAe: nonAeIncome };
  });
}
```

### Step 3 — Fix the conjoint segment rendering

The chart legend shows "Vous" and "Conjoint" but the bars appear to be single-colour. Confirm whether the conjoint income is being passed as a separate data series to the chart. If not:

- Split the income data into `user_ae_income` and `conjoint_income` series
- Pass both to the bar chart as stacked segments
- "Vous" segment = AE income (teal, already working)
- "Conjoint" segment = non-AE/conjoint income (purple, should stack on top)

This will also make it visually clear that the 7,600€ is composed of 6,600€ AE + 1,000€ conjoint.

### Step 4 — Verify chart label format

After fixing growth, 2035 will show ~12,840€. Confirm the Y-axis and bar labels format correctly for values above 10,000€ (e.g., "12.8k€" not "12840€").

---

## SCOPE BOUNDARY

**DO NOT:**
- Change the projection engine (HOTFIX-1 handles that)
- Add new chart types or chart libraries
- Show charges/net in this chart — it is a gross revenue timeline only
- Add more than 10 years to the chart range (keep existing range)

**ONLY:**
- Apply `(1 + growth_rate) ** year` to AE income in the chart's data source
- Fix conjoint income rendering as a separate stacked segment
- Verify Y-axis labels handle values > 10k€ correctly

Estimated change: ~20–30 lines in 1–2 files.

---

## Verification

After deploying (with HOTFIX-1 already live):

1. **Timeline chart 2026:** shows 7,600€ (6,600 AE + 1,000 conjoint) — unchanged ✓
2. **Timeline chart 2031:** shows ~10,180€ (8,815 AE grown 6%×5 + 1,000 conjoint) — was 7,600€
3. **Timeline chart 2035:** shows ~12,840€ — was 7,600€
4. **Bars are two-colour stacked:** teal (AE, growing) + purple (conjoint, flat)
5. **Horizon tab projection table** unchanged — HOTFIX-1 already fixed that

---

## DONE WHEN

- [ ] Timeline chart shows growing AE income year over year at 6%
- [ ] 2035 bar shows ~12,840€ (not 7,600€)
- [ ] Conjoint income renders as separate stacked segment in purple
- [ ] Bar labels/Y-axis handle values > 10,000€ correctly
- [ ] Chart data is consistent with Horizon tab projection values for the same years
