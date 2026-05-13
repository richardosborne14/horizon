# HOTFIX-3: Fix Conjoint Salary Earner Field + Apply Spouse Social Charges

**Severity:** HIGH  
**Discovered:** 2026-05-12 via DB audit  
**Run after:** HOTFIX-1 and HOTFIX-2 are deployed and verified.

## Problem

Three related issues share a single root cause — the "Salaire (conjoint)" income source was created with `earner='user'` instead of `earner='spouse'`:

1. **Spouse social charges never deducted.** Caro's 1,000€/month gross CDI salary should have ~23% social charges deducted, giving ~770€ net. Instead the full 1,000€ is treated as cost-free non-AE income, overstating household net income by ~230€/month (2,760€/year).

2. **Spouse table not populated.** The `spouses` table row for Caro has `monthly_gross_income = null`. The `_compute_spouse_charges()` function reads from this field — so even if the charge logic exists, it never fires.

3. **Identity page income field is blank.** The "Revenu brut mensuel (€)" field in the Conjoint(e) section reads from `spouses.monthly_gross_income`. Since it's null, the field shows empty, misleading the user into thinking Caro's income isn't recorded anywhere.

---

## Root Cause

When the "Salaire (conjoint)" income source was created via the UI, the `earner` field was set to `'user'` instead of `'spouse'`. The `spouses` table was never updated to mirror this income. The two data stores (income_sources and spouses) are out of sync.

---

## Fix

This fix has three parts: correct the data, sync the spouse record, and ensure the projection engine deducts spouse charges correctly.

### Part A — Correct the income_sources earner field

Run a targeted DB update scoped to this specific income source. Do not write a generic migration. The income source to fix is identifiable by:
- `label = 'Salaire (conjoint)'` (or similar)
- `earner = 'user'`
- `is_ae_revenue = false`
- `user_id = '67b56986-89c3-4ff5-808e-d3177507d341'`

```sql
UPDATE income_sources
SET earner = 'spouse'
WHERE user_id = '67b56986-89c3-4ff5-808e-d3177507d341'
  AND is_ae_revenue = false
  AND earner = 'user'
  AND label ILIKE '%conjoint%';
```

Verify exactly 1 row is updated. If 0 or >1, stop and investigate before proceeding.

### Part B — Sync the spouses table

After correcting the earner, populate `spouses.monthly_gross_income` from the income source amount. Also write a backend function (if it doesn't exist) that keeps these in sync going forward when a spouse income source is saved.

```sql
UPDATE spouses
SET monthly_gross_income = 1000.00
WHERE user_id = '67b56986-89c3-4ff5-808e-d3177507d341';
```

After this, the identity page "Revenu brut mensuel" field for Caro will display 1,000€ correctly.

**Going forward (application logic):** When a user saves an income source with `earner='spouse'` and `is_ae_revenue=false`, the backend should upsert `spouses.monthly_gross_income` with the sum of all such sources. Add this sync call to the income source save handler. ~10 lines.

### Part C — Verify spouse charges are deducted in the projection

The projection engine has a `_compute_spouse_charges()` function (or equivalent). It reads `spouses.monthly_gross_income` and applies a ~23% deduction for salaried social charges. After Part B, this will now have a value to work with.

Locate the function and trace its call in the main projection loop. Confirm:

```python
# This should now fire correctly after Part B:
spouse_gross_annual = spouse.monthly_gross_income * 12  # 12,000€
spouse_charges = spouse_gross_annual * 0.23             # 2,760€
spouse_net_annual = spouse_gross_annual - spouse_charges # 9,240€

# total_income should use spouse_net_annual, not spouse_gross_annual
total_income = user_ae_net + user_non_ae_net + spouse_net_annual
```

If `_compute_spouse_charges()` already exists and is already wired into `total_income` — and just wasn't firing because `monthly_gross_income` was null — then Part B alone may be sufficient. Confirm by checking the NET column in the projection after the fix.

If the function exists but its output is not subtracted from `total_income`, wire it in now.

---

## SCOPE BOUNDARY

**DO NOT:**
- Change how AE charges are computed
- Add new income source types or UI fields
- Modify the income_sources table schema
- Apply growth rate to spouse salary (it's a fixed CDI salary — use 0% growth or a separate spouse growth rate if one exists; do not apply the user's AE growth_rate)
- Touch any other user's data

**ONLY:**
- Update the one income source row's earner field
- Update spouses.monthly_gross_income to 1000.00
- Add the spouse income sync call on income source save
- Confirm `_compute_spouse_charges()` fires and its result reduces total_income

Estimated change: 1 SQL update + ~15 lines of application logic.

---

## Verification

After deploying:

1. **Identity page** → Caro's "Revenu brut mensuel" shows **1,000€** (not blank)
2. **DB check:** `SELECT earner FROM income_sources WHERE label ILIKE '%conjoint%'` → returns `'spouse'`
3. **DB check:** `SELECT monthly_gross_income FROM spouses WHERE user_id = '67b56986...'` → returns `1000.00`
4. **Waterfall** (HOTFIX-2 must be deployed): "Autres revenus" shows 1,000€ gross; if spouse charges are shown net, it shows ~770€
5. **Projection NET 2026:** should decrease by ~2,760€/year (~230€/month) vs post-HOTFIX-1 values — this is expected and correct
6. **No other income sources affected** — verify no other rows were changed

---

## DONE WHEN

- [ ] `income_sources` row for Salaire (conjoint) has `earner = 'spouse'`
- [ ] `spouses.monthly_gross_income` = 1000.00 for this user
- [ ] Identity page shows Caro's income as 1,000€
- [ ] Projection deducts ~2,760€/year in spouse social charges from total income
- [ ] Projection NET 2026 is lower by ~2,760€ vs HOTFIX-1 baseline (correct — was previously overstated)
- [ ] Income source save handler syncs spouses.monthly_gross_income going forward
