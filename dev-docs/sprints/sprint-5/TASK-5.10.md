# TASK-5.10: Investment Model Refinement

**Status:** TODO
**Sprint:** 5
**Priority:** P2 (medium — improves accuracy, not a visible bug)
**Est. effort:** 2 hr
**Dependencies:** TASK-4.1

## Context

The current investment compounding model in the projection engine uses a simplified formula:

```python
eff_rate = max(Decimal("0.005"), spec["rate"] - inflation_rate * Decimal("0.25"))
```

This "effective real return" heuristic has several issues:
1. **Only 25% of inflation is subtracted** — meaning projections are systematically optimistic. In a 3% inflation scenario, a 7% PEA return becomes 6.25% instead of a more realistic 4% real return.
2. **The 0.5% floor is too low** — in high-inflation scenarios, guaranteed-capital vehicles (Livret A, LDDS) should track inflation, not return 0.5%.
3. **Livret A/LDDS rates are not fixed** — they're set by the government and typically track inflation. The model treats them as fixed at 2.5%.
4. **Tax treatment is oversimplified** — PFU is 30% (17.2% PS + 12.8% IR), not just the 17.2% currently used for AV/PEA. After 8 years on AV or 5 years on PEA, only PS applies. The model doesn't track holding period.
5. **No distinction between contribution growth and return growth** — the model compounds `bal + contrib + returns` but doesn't differentiate between the cost basis and gains (matters for tax calculation).

## Requirements

### Refinement 1: Real Return Calculation

1. **Replace the heuristic** with a clearer model:
   ```python
   # Nominal return
   nominal_return = spec["rate"]
   
   # For regulated savings (Livret A, LDDS): rate tracks inflation
   # In optimistic/moderate scenarios, rate = max(current_rate, inflation)
   # In pessimistic scenarios, rate stays fixed (government may not adjust)
   if spec.get("regulated", False):
       if scale == "pessimistic":
           effective_rate = nominal_return
       else:
           effective_rate = max(nominal_return, inflation_rate)
   else:
       # Market-based returns: subtract full inflation for real return
       # but keep nominal for compounding (the display shows nominal wealth)
       effective_rate = nominal_return
   
   # Apply scale adjustment
   scale_adj = {"optimistic": Decimal("1.1"), "moderate": Decimal("1.0"), "pessimistic": Decimal("0.8")}
   effective_rate = effective_rate * scale_adj[scale]
   ```

2. **Add `regulated: True` flag** to Livret A and LDDS in `VEHICLE_SPECS`.

### Refinement 2: Tax Treatment Accuracy

3. **Track holding period** for AV and PEA:
   - If the user has an existing balance, assume the vehicle was opened before the projection starts
   - For AV: after 8 years, only 17.2% PS on gains (with 4,600€ annual abattement for single, 9,200€ for couple)
   - For PEA: after 5 years, only 17.2% PS on gains
   - Before maturity: 30% PFU on gains

4. **Update tax calculation in the engine:**
   ```python
   years_held = year - projection_start_year  # Simplified assumption
   
   if vehicle == "pea":
       if years_held >= 5 or has_existing_balance:
           tax_rate = Decimal("0.172")  # PS only
       else:
           tax_rate = Decimal("0.300")  # PFU
   elif vehicle in ("av_euro", "av_uc"):
       if years_held >= 8 or has_existing_balance:
           # PS only on gains above abattement
           tax_rate = Decimal("0.172")
       else:
           tax_rate = Decimal("0.300")  # PFU
   ```

5. **PER exit taxation:**
   - Contributions were tax-deductible (IR savings during contribution phase)
   - At retirement: contributions taxed as income (IR), gains taxed at PFU
   - For MVP: apply a blended rate estimate (e.g., 20% on total withdrawal)
   - Add comment: this is approximate; actual PER exit taxation depends on marginal tax rate at retirement

### Refinement 3: Ceiling Behavior

6. **Handle Livret A ceiling more realistically:**
   - Current behavior: `new_bal = min(new_bal, ceiling * infl)` — ceiling grows with inflation
   - Issue: Livret A ceiling is set by law (22,950€ in 2024), not inflation-indexed
   - Fix: Use nominal ceiling, don't inflate. Only inflate investment ceilings that are genuinely inflation-linked (like PEA at 150,000€ — though PEA ceiling is also nominal)
   - When balance hits ceiling: redirect overflow to the next vehicle in priority order (Livret A → LDDS → AV euro)

7. **Add overflow redirect logic:**
   ```python
   if new_bal > ceiling:
       overflow = new_bal - ceiling
       new_bal = ceiling
       # Redirect overflow to next vehicle in priority
       redirect_to = get_overflow_target(vehicle_key)
       if redirect_to:
           balances[redirect_to] += overflow
   ```

### Refinement 4: Display Precision

8. **Show both nominal and real wealth** in the projection summary:
   - Nominal: what the numbers actually say (163.9k€)
   - Real (inflation-adjusted to today's euros): what it's worth in purchasing power
   - Display: "163.9k€ (≈ 112k€ en euros 2026)" using the moderate inflation rate

9. **Add to projection table:** Optional row or toggle showing "valeur réelle" vs "valeur nominale."

## Acceptance Criteria

- [ ] Regulated savings (Livret A, LDDS) track inflation in optimistic/moderate scenarios
- [ ] Tax rates differentiate between pre-maturity (PFU 30%) and post-maturity (PS 17.2%)
- [ ] Savings ceilings are nominal, not inflation-adjusted
- [ ] Overflow logic redirects excess savings to next-priority vehicle
- [ ] Real (inflation-adjusted) wealth displayed alongside nominal
- [ ] Projection results change meaningfully vs. current model (quantify the delta in tests)
- [ ] Unit tests for each refinement
- [ ] Hand-verified: Livret A at ceiling with 500€/month → overflow redirected correctly
- [ ] LEARNINGS.md updated

## Notes

- These refinements individually have modest impact but collectively they improve the engine's credibility. A financially literate user who sees Livret A returning 0.5% in a high-inflation scenario will question the entire model.
- The holding period tracking is a simplification — we assume existing balances have been held long enough for favorable tax treatment. This is reasonable for most users.
- The real vs nominal wealth display is an educational feature — most people don't intuitively understand that 163k€ in 2055 is worth much less than 163k€ today. Showing both numbers is a service to the user.
- Don't over-engineer the tax model. AE users don't file complex tax returns. The goal is "directionally correct" not "replaces an accountant."
