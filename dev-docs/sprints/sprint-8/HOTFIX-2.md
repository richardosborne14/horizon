# HOTFIX-2: Waterfall "Où va votre argent" Excludes Conjoint Salary from Display

**Severity:** HIGH (display bug — misleading to user, not a calculation error)  
**Discovered:** 2026-05-12 via live UI audit  
**Symptom:** The "Où va votre argent" waterfall on the Revenus page shows CA brut = 6,600€ and computes a **−194€ déficit**. The 1,000€/month conjoint salary is present in `income_sources` and IS included in the full projection engine (NET column in the projection table is correct), but the waterfall component does not fetch or display it. The user sees a false deficit that does not reflect their actual monthly position.  
**Impact:** The most prominent cashflow display in the app tells the user they are losing money every month. In reality the household is ~+800€/month positive after savings.

---

## Root Cause

The waterfall component fetches and displays only the user's AE revenue from `income_sources` (where `is_ae_revenue=True` and `earner='user'`). It does not include:

1. Non-AE income sources with `earner='user'` (e.g. the "Salaire (conjoint)" which has `earner='user'` due to a mislabelling bug)
2. Income sources with `earner='spouse'` (correctly scoped, but not shown)

The waterfall was likely built before the conjoint income feature existed, and was never updated to account for household income beyond AE revenue.

**Secondary note:** The "Salaire (conjoint)" source has `earner='user'` in the DB (a pre-existing data bug — it should be `earner='spouse'`). This task does NOT fix that data bug. It fixes the waterfall to show ALL income sources regardless of earner, so the display is correct whether or not the earner field is fixed later.

---

## Fix

### Step 1 — Locate the waterfall data fetch

Find the frontend component or API endpoint that powers the "Où va votre argent" section. It will either:
- Call a dedicated `/api/cashflow-waterfall` endpoint, or
- Compute values inline from the Revenus store/state

Look for where `ca_brut`, `cotisations`, `depenses_base`, and `vie` are assembled into the waterfall rows.

### Step 2 — Identify what income is being fetched

The component currently uses only AE income. Find the line that sets the income figure — it will look something like:

```python
# Backend (if API endpoint):
ae_income = sum(s.amount_monthly for s in sources if s.is_ae_revenue and s.earner == 'user')
# OR
ae_income = monthly_gross_ca  # fallback
```

```javascript
// Frontend (if computed in store):
const aeIncome = incomeSources.filter(s => s.is_ae_revenue).reduce(...)
```

### Step 3 — Add non-AE and conjoint income rows

The waterfall must show ALL household income. Add a separate line for non-AE income directly below the AE cotisations block:

```
CA brut (AE)          6 600€
Cotisations AE       −1 729€
Net AE après cotis.   4 871€
+ Autres revenus      1 000€   ← NEW LINE (salary, conjoint, etc.)
─────────────────────────────
Revenu total net      5 871€
Dépenses base        −4 015€
Vie (enfants, etc.)    −597€
Aides & crédits         +72€
─────────────────────────────
Revenu disponible     1 261€
Épargne prévue         −500€
─────────────────────────────
Solde mensuel          +761€   ← now correctly positive
```

**Backend change (if API-driven):**
```python
def get_cashflow_waterfall(user_id: str, year: int = 0):
    sources = get_income_sources(user_id)
    
    ae_monthly = sum(
        s.amount_monthly for s in sources 
        if s.is_ae_revenue
    )
    
    non_ae_monthly = sum(
        s.amount_monthly for s in sources 
        if not s.is_ae_revenue   # includes conjoint salary regardless of earner field
    )
    
    ae_rate = get_ae_rate(user.ae_activity_type, year)
    cfe_monthly = get_cfe_estimate(year) / 12
    ae_net = ae_monthly * (1 - ae_rate) - cfe_monthly
    
    total_net_income = ae_net + non_ae_monthly
    # ... rest of waterfall unchanged
    
    return {
        "ae_brut": ae_monthly,
        "cotisations": ae_monthly * ae_rate + cfe_monthly,
        "ae_net": ae_net,
        "autres_revenus": non_ae_monthly,   # ← NEW
        "total_net": total_net_income,       # ← NEW (replaces ae_net as the subtotal)
        "depenses_base": ...,
        "vie": ...,
        "aides_credits": ...,
        "revenu_disponible": ...,
        "epargne": ...,
        "solde": ...
    }
```

**Frontend change:**
Add a new waterfall row for `autres_revenus` between "Net AE après cotis." and "Dépenses base". Label it "Autres revenus (conjoint, etc.)" or dynamically use the source labels if there's only one. Show it in the same teal/positive colour as the CA brut row.

### Step 4 — Update the "Déficit / Solde" label logic

Currently the label shows "Déficit" in red when the value is negative. After the fix it will be positive. Ensure:
- Positive value → label "Solde mensuel", colour green/teal
- Negative value → label "Déficit", colour red
- Zero → label "Équilibre", colour neutral

This logic may already exist but be unreachable due to the missing income.

### Step 5 — Update the revenue timeline chart (Revenus page)

The "Timeline des revenus" bar chart (showing 7,600€ flat for all years) correctly shows total household gross income. Confirm it already includes the conjoint salary — if it does, no change needed. If it only shows AE income, apply the same fix: sum all `income_sources` regardless of `is_ae_revenue` or `earner`.

---

## SCOPE BOUNDARY

**DO NOT:**
- Fix the `earner='user'` vs `earner='spouse'` data bug on the Salaire (conjoint) source — that is a separate data correction
- Add spouse social charge deduction to the waterfall — the earner bug must be fixed first, and that deduction belongs in a separate task
- Change the projection engine's NET calculation — it is already correct
- Modify the Horizon tab projection table
- Add new income sources or UI for adding income

**ONLY:**
- Fetch all `income_sources` (not just AE) in the waterfall data layer
- Add one new row "Autres revenus" to the waterfall display
- Ensure the solde/déficit label switches correctly based on sign
- Optionally verify the timeline chart is already summing all sources

Estimated change: ~20–30 lines across 1 backend file + 1 frontend component.

---

## Verification

After applying the fix, check the Revenus page waterfall for user `richard@digitalbricks.io`:

1. **"Autres revenus" row appears** showing 1,000€ (the Salaire conjoint)
2. **"Revenu disponible"** shows ~1,261€ (not 306€)
3. **"Solde mensuel"** shows ~+761€ in green (not −194€ in red)
4. **The red "Déficit" banner is gone**
5. **The projection table NET column is unchanged** — it was already correct

---

## DONE WHEN

- [ ] Waterfall fetches all income sources, not only AE sources
- [ ] New "Autres revenus" row visible in waterfall showing 1,000€
- [ ] Revenu disponible ≈ 1,261€
- [ ] Solde mensuel ≈ +761€, displayed in teal/green
- [ ] "Déficit −194€" red banner no longer appears
- [ ] Projection table NET column values unchanged (regression check)
- [ ] Timeline chart on Revenus page confirmed to include all sources (or fixed if not)
