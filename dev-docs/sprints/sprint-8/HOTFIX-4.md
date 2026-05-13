# HOTFIX-4: Caro's Career History Missing — Pension Gap Alert + Projection Inclusion

**Severity:** HIGH (silent omission — no error, just wrong retirement numbers)  
**Discovered:** 2026-05-12 via screenshot audit  
**Run after:** HOTFIX-3 (spouse record must be correctly populated first)

## Problem

Caro's "Parcours de Caro" section shows **0 / 172 trimestres validés** with "Aucune période enregistrée pour le conjoint." She is recorded as CDI status, born 1982-11-24 (currently 43 years old). A CDI employee of 43 has been accumulating pension trimestres for likely 15–20+ years.

Consequences:
1. **Her pension is entirely absent from the household retirement projection.** The Horizon tab shows only Richard's pension (1,415€/month). Caro's pension could realistically be 1,000–1,300€/month at her retirement age — a massive blind spot in the long-term picture.
2. **No alert or prompt surfaces this gap.** The app knows Caro is CDI but shows no warning that her career history is empty. The user has no reason to know this matters.
3. **The retirement income picture is structurally incomplete** as long as she is a major household earner with an untracked pension trajectory.

---

## Root Cause

The career history UI and pension calculation for the primary user (Richard) was built in a prior sprint. The same infrastructure exists for the conjoint ("Parcours de Caro" section is visible in the UI). However, no data has been entered, and the system does not prompt the user to fill it in even when the conjoint is marked as a salaried employee (CDI/CDI-equivalent) with no periods recorded.

---

## Fix

This task has two parts: add a missing-data alert to prompt career history entry, and ensure Caro's pension feeds into the household projection once data exists.

### Part A — Lifecycle alert for missing conjoint career history

Add one new alert to the existing lifecycle alert system. Fire it when ALL of the following are true:
- A spouse/conjoint exists on the user account
- `spouse.status` is `'cdi'`, `'fonctionnaire'`, or another salaried status (i.e. not `'ae'`, `'retired'`, `'inactive'`)
- The spouse has zero career history periods recorded
- The spouse is between ages 25 and 62 (working age — no alert if very young or already at pension age)

Alert content:
```
Title:   "Retraite de Caro non estimée"
Body:    "Caro est enregistrée comme salariée mais aucune période de carrière n'a été 
          saisie. Sa retraite n'est pas incluse dans la projection du foyer. Ajoutez 
          son parcours pour voir l'impact complet."
Action:  Link → Identité page, scrolled to "Parcours de Caro" section
Severity: warning (orange)
```

Place this alert in the "Recommandations" section of the Horizon tab alongside the other advisory items. It should appear above lower-priority alerts when present.

Implementation: add the check to the existing `_generate_lifecycle_alerts()` function (or equivalent). ~15 lines.

### Part B — Include Caro's pension in household retirement projection

The pension estimation function for the primary user reads career history periods, computes trimestres validés, applies SAM calculation, and returns an estimated monthly pension. The same function should be callable for the spouse.

Locate `estimate_pension()` (or equivalent). Confirm it accepts a career history list and personal parameters (birth date, target retirement age). If it does:

1. Call it for Caro using her career history periods, birth date (1982-11-24), and her own retirement age (use Richard's target age as default if Caro has no separate target, or use French legal retirement age for her cohort: 64)
2. Store the result as `spouse_pension_monthly`
3. Add `spouse_pension_monthly` to `total_passive_income` in the retirement phase of the projection (years after Caro's retirement age)

```python
# In the projection loop, for years >= caro_retirement_year:
caro_pension = estimate_pension(
    career_periods=spouse_career_periods,
    birth_date=spouse.birth_date,
    retirement_age=64,  # legal age for her cohort
    target_trimestres=172
)
total_passive_income += caro_pension  # add to household retirement income
```

If `spouse_career_periods` is empty (as it currently is), `estimate_pension()` should return 0 gracefully — which is the current behaviour. No change to output until data is entered.

**Display:** On the Horizon tab retirement summary, show both pensions separately:
```
Estimation retraite — foyer
  Retraite (vous):    1 415€   [50% taux plein]
  Retraite (Caro):       0€   ⚠️ Aucune période saisie
  Total foyer:        1 415€
```

Once Caro's periods are entered, her pension appears automatically.

### Part C — Verify the Parcours de Caro UI already works

The "Parcours de Caro" section exists in the UI with a "+ Ajouter une période" button. Confirm that clicking this button:
1. Opens a period entry form (label/employer, start year, end year, annual gross salary)
2. Saves the period to the career history table with `earner='spouse'`
3. Updates the trimestres counter immediately

If any of these steps are broken or missing, fix them. If the UI works correctly, no changes needed — just verify.

---

## SCOPE BOUNDARY

**DO NOT:**
- Build a salary history import feature or external data integration
- Change the pension estimation formula or trimestres calculation
- Add a separate retirement age field for the spouse (use 64 as default for her cohort)
- Redesign the Parcours section UI
- Generate default/estimated career periods automatically — the user must enter real data

**ONLY:**
- Add one lifecycle alert when spouse is salaried with zero career periods
- Wire Caro's pension output into household total_passive_income in the projection
- Show Caro's pension as a separate line in the retirement summary display
- Verify the career period entry UI works end-to-end

Estimated change: ~40 lines across 2–3 files.

---

## Verification

1. **Horizon tab → Recommandations:** "Retraite de Caro non estimée" warning appears (orange) with link to career section
2. **Horizon tab → Estimation retraite:** shows two pension lines — Richard's 1,415€ and Caro's 0€ with warning indicator
3. **Add one test career period for Caro** (e.g., 2005–2026, 30,000€/year) → trimestres counter updates, pension estimate appears, total foyer pension increases
4. **Remove the test period** → revert to 0€ and warning reappears
5. **Alert disappears** if Caro's status is changed to 'ae' or 'inactive'

---

## DONE WHEN

- [ ] Lifecycle alert "Retraite de Caro non estimée" visible on Horizon tab when spouse has no career periods and is salaried
- [ ] Alert links to Parcours de Caro section
- [ ] Retirement summary shows two pension lines (Richard + Caro) with individual amounts
- [ ] Caro's pension feeds into total household passive income in projection years after her retirement
- [ ] Adding a career period for Caro updates trimestres count and pension estimate in real time
- [ ] Zero career periods → 0€ pension (no crash, no default estimation)
