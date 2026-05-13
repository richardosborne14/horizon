# HOTFIX-1: Income Growth Not Applied in `income_sources` Projection Path

**Severity:** CRITICAL  
**Discovered:** 2026-05-12 via live projection audit  
**Symptom:** CA BRUT is flat at 79,200€ across all 30 projection years despite user selecting 6% "Ambitieux" growth. VIE expenses inflate correctly at 3%/year. The resulting scissors effect makes NET go sharply negative by year 10, falsely triggering "patrimoine épuisé à 76 ans" and "dépenses > revenus en 2028" alarms.  
**Impact:** Every user with income_sources entered sees a catastrophically wrong long-term projection. All advisory output (alerts, recommendations, goal solver) is based on corrupt data.

---

## Root Cause

The projection engine has two code paths for computing annual revenue:

**Path A — fallback (no income_sources):**
```python
gross = monthly_gross_ca * 12 * (1 + growth_rate) ** year
```
Growth is applied. ✅

**Path B — income_sources path (active for this user):**
```python
user_ae_income = compute_income_for_year(sources, year, "user", ae_only=True)
# returns: sum of source.amount_monthly * 12 for all matching sources
# growth_rate is NEVER APPLIED ❌
```

`compute_income_for_year()` sums fixed monthly amounts from the DB. It has no knowledge of `growth_preset` or `growth_rate`. The result is the same 79,200€ in year 0 and year 29.

The user's `growth_preset = 'ambitious'` maps to `growth_rate = 0.06`. This rate is used in Path A but ignored in Path B.

---

## Fix

### Step 1 — Locate `compute_income_for_year()`

Find the function in the backend. It will be in the projection engine file (likely `projection_engine.py`, `income_utils.py`, or similar). It accepts `sources`, `year`, `earner`, and optionally `ae_only`. It currently returns a flat sum.

### Step 2 — Add `growth_rate` parameter

Change the function signature to accept an optional growth rate:

```python
def compute_income_for_year(
    sources: list,
    year: int,
    earner: str,
    ae_only: bool = False,
    growth_rate: float = 0.0   # ADD THIS
) -> float:
    total = 0.0
    for source in sources:
        if source.earner != earner:
            continue
        if ae_only and not source.is_ae_revenue:
            continue
        # Apply compound growth to this source's base monthly amount
        annual = source.amount_monthly * 12 * (1 + growth_rate) ** year
        total += annual
    return total
```

**Important:** Apply growth only to AE sources (those with `is_ae_revenue=True`). Non-AE sources (salary, passive income) should NOT be grown by the user's AE growth rate — they have their own growth logic or are fixed. Pass `growth_rate=0.0` when calling for non-AE earners unless a separate spouse growth rate exists.

### Step 3 — Pass `growth_rate` at the call site

Find where `compute_income_for_year()` is called inside the main projection loop. The user's `growth_rate` is already computed from `growth_preset` at this point (it's used in Path A). Pass it through:

```python
# BEFORE (broken):
user_ae_income = compute_income_for_year(sources, year, "user", ae_only=True)

# AFTER (fixed):
user_ae_income = compute_income_for_year(
    sources, year, "user", ae_only=True, growth_rate=growth_rate
)
```

Do NOT pass `growth_rate` to non-AE calls:
```python
# Non-AE income (salaries, conjoint) — no growth from AE preset:
user_non_ae = compute_income_for_year(sources, year, "user", ae_only=False, growth_rate=0.0)
# Subtract ae to get non-ae only:
user_non_ae = user_non_ae_total - user_ae_income  # or filter differently
```

### Step 4 — Verify AE charges scale with grown income

After the fix, `gross` (the base for AE charge calculation) must use the grown income:

```python
gross = user_ae_income  # now correctly: 6600*12 * 1.06**year
charges = gross * ae_rate
```

This should already be the case if the charges calculation reads from `user_ae_income`. Confirm it does.

### Step 5 — Do NOT change the CA BRUT display column

The projection table's "CA BRUT" column should now show the grown value (e.g., 79.2k€ in year 0, 106k€ in year 5, 142k€ in year 10). Do not cap or flatten it. The display is correct as-is once the underlying value changes.

---

## SCOPE BOUNDARY

**DO NOT:**
- Add a per-source growth_rate field to the income_sources table or UI
- Change the growth_rate computation logic or presets
- Touch the Path A fallback — it already works
- Modify the spouse income path (different issue, different task)
- Add new tests beyond the verification queries below
- Refactor `compute_income_for_year()` beyond adding the one parameter

**ONLY:**
- Add `growth_rate: float = 0.0` parameter to `compute_income_for_year()`
- Apply `(1 + growth_rate) ** year` to AE source amounts inside that function
- Pass `growth_rate=growth_rate` at the one (or few) AE call sites in the projection loop

Estimated change: ~10 lines modified across 1–2 files.

---

## Verification

After applying the fix, run a projection for user `richard@digitalbricks.io` and confirm:

1. **Projection table CA BRUT column** grows year over year:
   - 2026: ~79.2k€
   - 2031: ~106k€  
   - 2036: ~142k€
   - 2041: ~190k€

2. **COTIS column** scales proportionally with grown CA (not flat):
   - 2026: ~20.8k€ (26.2%)
   - 2031: ~30.2k€ (28.5% of 106k)

3. **NET column** is positive and grows through working years:
   - 2026: ~15k€ ✓
   - 2031: should be ~+25k€ (not −7k€)
   - 2036: should be ~+40k€ (not −31k€)

4. **"Dépenses > revenus en 2028" alert** disappears from the advisory panel.

5. **Patrimoine épuisé** warning either disappears or moves well beyond age 76.

---

## DONE WHEN

- [ ] `compute_income_for_year()` has `growth_rate` parameter defaulting to 0.0
- [ ] Growth is applied as `amount_monthly * 12 * (1 + growth_rate) ** year` for AE sources
- [ ] Call site passes `growth_rate=growth_rate` for AE income computation
- [ ] Projection table CA BRUT shows ~106k€ in 2031 for this user (not 79.2k€)
- [ ] NET column is positive for years 2026–2050 in the base case
- [ ] No other projection output is broken (VIE, ENFANTS, PATRIMOINE columns unchanged in logic)
