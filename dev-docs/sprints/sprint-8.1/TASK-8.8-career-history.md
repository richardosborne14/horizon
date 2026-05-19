# TASK-8.8 — Career History: Chômage, Internship, SASU Gérant Type, Gap Detector

## Background
The career history page currently supports CDI, CDD, AE, SASU, and free-text periods.
Several important period types are missing, and the system has no way to detect or flag
unrecorded gaps. This causes silent pension underestimates.

## 4 improvements in this task

---

## 8.8.A — Add "Chômage indemnisé" period type

### Why it matters
In France, each month of Pôle Emploi (France Travail) allocation indemnisée validates
**1 trimestre** for the base pension (régime général), regardless of earnings.
For Richard, the 2017–2020 gap may contain up to 12 trimestres of chômage.

### What to add

**New period_type: `chomage`**

DB: no schema change needed — `period_type` is a text field, just add a new enum value
in the frontend type definitions and pension calculation.

**Frontend — career form:**
Add "Chômage indemnisé (Pôle Emploi)" to the period type dropdown.
Required fields: start_date, end_date. No employer, no salary needed.
Help text: "Chaque mois d'allocation validée par Pôle Emploi ouvre droit à 1 trimestre."

**Pension calculation:**
In `pension.py`, for `period_type == "chomage"`:
```python
months = months_between(start, end)
trimestres_this_period = months  # 1 trimestre per month of allocation
# SAM contribution: chômage does NOT contribute to SAM (salary average)
# It only adds trimestres
```

---

## 8.8.B — Add "Stage rémunéré" period type

### Why it matters
A paid internship in France contributes trimestres IF the salary is above the threshold
(150 × SMIC per trimestre). For a year-long stage paid above minimum wage, this can
be 4 trimestres. It also contributes to the SAM if the annual salary qualifies.

### What to add

**New period_type: `stage`**

Frontend fields: start_date, end_date, employer_name, annual_gross (estimated).
Help text: "Un stage rémunéré peut valider des trimestres si le salaire brut est
≥ 150 × SMIC par trimestre (soit ~1 800 €/trimestre en 2026)."

**Pension calculation:**
In `pension.py`, treat `stage` like CDI/CDD for the general regime:
same trimestre-counting logic, same SAM contribution if salary qualifies.

---

## 8.8.C — SASU gérant type field

### Why it matters
A SASU director can be either:
- **Gérant majoritaire** (>50% shares): affiliated to SSI (ex-RSI) — pays TNS-style
  cotisations, different pension regime
- **Gérant minoritaire / assimilé salarié** (<50% shares): affiliated to régime général
  — pays salarial + patronal, equivalent to employee for pension purposes

The current schema has `pension_regime` but no gérant_type. Richard confirmed he was
gérant majoritaire (51%), meaning his SASU period should use SSI/TNS rates, not
régime général. This may affect trimestre count and SAM.

### What to add

**New field on career_periods: `sasu_gerant_type` (nullable text)**
Values: `"majoritaire"` | `"minoritaire"` | `"egal"` (50/50)

**Migration:**
```sql
ALTER TABLE career_periods ADD COLUMN sasu_gerant_type TEXT;
```

**Frontend — SASU period form:**
When `period_type == "sasu"`, show a radio group:
- "Gérant majoritaire (> 50% des parts)" → `sasu_gerant_type = "majoritaire"`
- "Gérant minoritaire (< 50% des parts)" → `sasu_gerant_type = "minoritaire"`
- "Gérant égalitaire (50/50)" → `sasu_gerant_type = "egal"`

Help text: "Cela détermine votre régime social (TNS ou assimilé salarié)."

**Pension calculation:**
In `pension.py`, for SASU periods:
```python
if period.sasu_gerant_type == "majoritaire":
    # TNS regime: trimestres validated like AE/TNS
    # Threshold: same SMIC-based formula
    # SAM: use actual salary for TNS-adjusted calculation
    regime = "ssi_tns"
else:
    # Assimilé salarié: régime général
    regime = "general"
```

For now, treating majoritaire as SSI/TNS with same trimestre thresholds as AE is
a sufficient approximation. Full TNS pension calculation is a future enhancement.

---

## 8.8.D — Career gap detector

### Why it matters
Silent gaps in career history are a leading cause of pension underestimates.
The system should detect and surface these proactively.

### What to add

**Backend: `detect_career_gaps()` utility in `calculations/pension.py`**

```python
def detect_career_gaps(
    career_periods: list,
    user_birth_date: date,
    current_date: date,
) -> list[dict]:
    """
    Find unrecorded calendar gaps in career history after age 18.
    Returns list of {start, end, months, user_age_start}
    Gaps < 3 months are ignored (holidays, transitions).
    """
    MIN_GAP_MONTHS = 3
    career_start = date(user_birth_date.year + 18, user_birth_date.month, 1)
    
    active_periods = sorted(
        [p for p in career_periods if p.is_active],
        key=lambda p: p.start_date
    )
    
    gaps = []
    cursor = career_start
    for period in active_periods:
        if period.start_date > cursor:
            gap_months = months_between(cursor, period.start_date)
            if gap_months >= MIN_GAP_MONTHS:
                gaps.append({
                    "start": cursor,
                    "end": period.start_date,
                    "months": gap_months,
                    "user_age_start": age_at(user_birth_date, cursor),
                })
        cursor = max(cursor, period.end_date or current_date)
    
    # Check for gap at end of recorded history up to today
    if cursor < current_date:
        gap_months = months_between(cursor, current_date)
        if gap_months >= MIN_GAP_MONTHS:
            gaps.append({
                "start": cursor,
                "end": current_date,
                "months": gap_months,
                "user_age_start": age_at(user_birth_date, cursor),
            })
    
    return gaps
```

**API: Include gap list in pension estimate response**

```json
{
  "trimestres_total": 162,
  "taux_plein_threshold": 172,
  "career_gaps": [
    {
      "start": "2017-06",
      "end": "2020-07",
      "months": 37,
      "user_age_start": 31,
      "potential_trimestres": 12
    }
  ]
}
```

**Frontend: Career page shows gap banners**

In the career timeline on `/identity`, for each detected gap:
```svelte
<div class="gap-banner">
  <span class="gap-icon">⚠️</span>
  <div>
    <strong>Période non enregistrée : {formatDate(gap.start)} – {formatDate(gap.end)}</strong>
    <p>
      {gap.months} mois manquants (~{Math.floor(gap.months/3)} trimestres potentiels).
      Étiez-vous en chômage, congé parental, à l'étranger ou en formation ?
    </p>
    <small>
      💡 Pensez aussi aux congés maternité/paternité, arrêts maladie longue durée
      et périodes d'invalidité — ils peuvent tous valider des trimestres.
    </small>
    <button on:click={() => addPeriodForGap(gap)}>+ Ajouter une période ici</button>
  </div>
</div>
```

The "Ajouter une période ici" button pre-fills the start/end dates in the add-period form.

---

## DONE WHEN
- [ ] Period type "chomage" exists and validates 1 trimestre/month in pension.py
- [ ] Period type "stage" exists and validates trimestres if salary qualifies
- [ ] `sasu_gerant_type` column added, migration created
- [ ] SASU form shows gérant type radio buttons when period_type = sasu
- [ ] Pension calculation uses SSI/TNS logic for majoritaire, régime général for minoritaire
- [ ] `detect_career_gaps()` correctly identifies Richard's 2017–2020 gap (37 months)
- [ ] Career page shows gap banners with actionable "Ajouter une période" button
- [ ] Gap banners include reminder about congé parental, maladie, and chômage
- [ ] Pension estimate API returns `career_gaps` array
- [ ] Unit test: Richard's 3 active periods → 1 gap detected (2017-06 to 2020-07)
