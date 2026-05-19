# TASK-8.10 — Property Classification: Primary Residence vs Rental in Net Worth

## Problem
The net worth form has a single `property_primary_value` field and an `property_other_value`
field. There is no way to know if the "other property" is:
- A rental property generating income (already partially modeled in Projects)
- A secondary residence (vacation home)
- Land

More critically, the system needs to understand which properties are the user's HOME
(non-income-generating, cannot apply 4% rule) vs which properties produce income.

## SCOPE BOUNDARY — DO NOT
- DO NOT build a full real estate management module
- DO NOT change the Projects schema for investment properties
- DO NOT change the property appreciation calculation

---

## Implementation steps

### Step 1 — Add `residence_type` to net worth snapshot

**Migration:**
```sql
ALTER TABLE net_worth_snapshots 
  ADD COLUMN residence_type TEXT DEFAULT 'primary_residence';
  -- Values: 'primary_residence', 'rental', 'secondary', 'land'

ALTER TABLE net_worth_snapshots
  ADD COLUMN property_other_type TEXT DEFAULT 'none';
  -- Values: 'none', 'rental', 'secondary', 'land'
```

### Step 2 — Frontend: net worth form

In the net worth form, add:
- Label clarification on `property_primary_value`: "Valeur de votre résidence principale"
  with a note: "Ne génère pas de revenus — non incluse dans le calcul de revenu passif."
- For `property_other_value`: show a dropdown "Type de bien" with:
  - "Aucun autre bien" (default)
  - "Résidence secondaire"
  - "Bien locatif" → note: "Si vous avez un projet immobilier locatif, configurez-le dans 'Projets'"
  - "Terrain / autre"

### Step 3 — Backend: clarify the 4% rule separation

The fix from TASK-8.2 already handles this correctly (only liquid investments use 4% rule).
This task just ensures the UI is clear and doesn't mislead users about what drives
passive income.

### Step 4 — Inform user about the House project

If the user has a `property_other_value > 0` AND `property_other_type = "rental"`,
but no active invest-type Project, show a suggestion:
"Vous avez un bien locatif. Avez-vous configuré ses revenus dans la section Projets?"

---

## DONE WHEN
- [ ] Net worth form has clear labels distinguishing primary vs other property
- [ ] `property_other_type` dropdown exists with 4 options
- [ ] Note on primary residence confirms it's not part of passive income calculation
- [ ] If rental property + no invest project → suggestion banner shown
- [ ] Migration created and run

---
---

# TASK-8.11 — Fix Car Entity: Sync replace_cost Metadata with Cost Events

## Problem
When a user edits a car entity's replacement cost (via the `replace_cost` metadata field),
the cost events (`c-replace-*`) are NOT updated. Currently both cars show:
- Metadata `replace_cost: 18,000€`
- Cost events `c-replace-*`: 10,000€

This is a 44% underestimate of car replacement costs per event.

## Root cause
The `replace_cost` in metadata and the amounts in `cost_events` are stored separately.
Editing one doesn't update the other. The user corrected the cost events manually to
10,000 (their actual target), but the metadata still shows 18,000 from the default.
The bug is that these two values can drift out of sync silently.

## SCOPE BOUNDARY — DO NOT
- DO NOT change the cost event schema
- DO NOT change how existing cost events are calculated in the projection engine
- DO NOT retroactively change the user's 10,000€ cost events — those are intentional

---

## Implementation steps

### Step 1 — When saving a car entity, sync replace_cost to all c-replace-* events

In the backend car entity save handler (PUT /api/life-entities/{id}):

```python
if entity.entity_type == "car":
    new_replace_cost = entity.metadata.get("replace_cost")
    if new_replace_cost:
        # Update all cost events of type c-replace-* with the new cost
        for event in entity.cost_events:
            if event["id"].startswith("c-replace-"):
                event["amount"] = float(new_replace_cost)
        # Save updated cost_events back
```

### Step 2 — Frontend: show replace_cost as an editable field in the car form

Currently the car form may have a hidden/metadata-only `replace_cost` field.
Make it a visible, labeled input: "Coût de remplacement estimé (€)".
When the user changes this, all replacement cost events update in real-time on the
client before save, so the user can see the impact.

### Step 3 — Display sync warning if metadata ≠ cost events

In the car entity display, if `metadata.replace_cost ≠ cost_event.amount` for any
c-replace-* event, show: "⚠️ Coût de remplacement inconsistant entre les paramètres
et les événements. Cliquez pour synchroniser."

---

## DONE WHEN
- [ ] Saving a car entity with updated replace_cost updates all c-replace-* event amounts
- [ ] Car form shows editable "Coût de remplacement" field
- [ ] Inconsistency warning shown if metadata ≠ events (for existing data)
- [ ] Richard's two cars: no inconsistency warning after first save

---
---

# TASK-8.12 — AE Pension: Use Projected Income, Not Static Career Period Value

## Problem
The pension estimate for Richard's AE period uses `annual_gross = 40,000€` from
the career_periods table. But his actual current CA is €79,200/year (6,600 × 12).
The career period was entered historically and never updated.

More importantly, the AE career period is open-ended (no end_date). For pension SAM
(Salaire Annuel Moyen — average of 25 best years), the engine should use the
**projected annual income** for each future year of the AE period, not a frozen past value.

## SCOPE BOUNDARY — DO NOT
- DO NOT change the career history schema
- DO NOT change how CDI/CDD/salaried period pension is calculated
- DO NOT change the trimestre counting logic (only the SAM contribution)

---

## Implementation steps

### Step 1 — In pension estimation, detect open-ended AE periods

In `calculations/pension.py`, in `estimate_monthly_pension_v2()`:

```python
for period in career_periods:
    if period.period_type == "ae" and period.end_date is None:
        # This is an ongoing AE period.
        # For years already elapsed: use actual income_sources projected values
        # For future years: use projected AE CA from the projection timeline
        period.annual_gross = get_ae_projected_annual(
            income_sources=inp.income_sources,
            growth_rate=inp.ae_growth_rate,
            current_year=current_year,
        )
```

### Step 2 — `get_ae_projected_annual()` utility

```python
def get_ae_projected_annual(income_sources, growth_rate, current_year) -> float:
    """
    Returns current-year projected AE annual income from active income sources.
    This is what should be used for pension SAM calculations for the current AE period.
    """
    ae_monthly = sum(
        s.amount for s in income_sources
        if s.is_active and s.is_ae_revenue and s.earner == "user"
    )
    return ae_monthly * 12
```

For simplicity, use the current year's value (not projected future — the SAM
already selects the best 25 years, so future growth will be reflected as income_sources
values grow year by year in the main projection).

### Step 3 — Rebuild SAM for AE periods using actual income data

The key change: when computing the 25-best-years SAM for pension estimation,
for each year of the ongoing AE period, use:

```
AE_revenu_pris_en_compte = ae_ca_that_year × (1 - abattement_bnc)
                         = ae_ca_that_year × 0.66   (for BNC 34% abattement)
```

Where `ae_ca_that_year` comes from the projection timeline (grows at `ae_growth_rate`).

### Step 4 — Add a "Vos revenus AE pour la retraite" note on the career page

In the career page, for open-ended AE periods, show:
"Revenus utilisés pour le calcul de la retraite : {fmtK(projected_ae_annual)}€/an
(base : vos sources de revenus AE actives). Pour modifier, mettez à jour vos
sources de revenus."

---

## DONE WHEN
- [ ] Open-ended AE periods use `income_sources` sum rather than `career_periods.annual_gross`
- [ ] `get_ae_projected_annual()` exists and returns 79,200 for Richard's current setup
- [ ] AE revenu_pris_en_compte for SAM uses 66% of projected CA
- [ ] Career page shows note explaining AE income used for pension
- [ ] Pension estimate for Richard shows materially higher AE SAM contribution (79,200 vs 40,000)
- [ ] Unit test: open AE period with income_sources sum of 6,600×12=79,200 → SAM contribution = 52,272
