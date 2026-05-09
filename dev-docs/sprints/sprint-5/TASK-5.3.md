# TASK-5.3: State Pension (Retraite) Estimation

**Status:** TODO
**Sprint:** 5
**Priority:** P1 (high — significantly affects post-retirement accuracy)
**Est. effort:** 2 hr
**Dependencies:** TASK-4.1

## Context

Every auto-entrepreneur paying cotisations sociales is building pension rights. Even at modest AE income levels, the combination of retraite de base (CNAV/CIPAV) and retraite complémentaire can represent 500–1,500€/month at retirement. Currently Horizon ignores this entirely, making the post-retirement picture systematically more pessimistic than reality.

The pension calculation is complex in full precision (trimestres, points, taux plein, décote, surcote...), but a reasonable estimation model is both achievable and valuable. We're not replacing info-retraite.fr — we're giving the user a ballpark so they can see the full picture.

## Requirements

### Backend: Pension Estimation Module

1. **Create `backend/app/calculations/pension.py`**:

   For AE (micro-entrepreneur), pension rights are based on CA, not on cotisations:

   **Retraite de base (CNAV for BIC, CIPAV for some BNC):**
   - Trimestres validés per year: based on CA thresholds (not hours worked)
     - BNC: 1 trimestre per ~2,880€ CA (2024 values), max 4/year
     - BIC services: 1 trimestre per ~2,540€ CA, max 4/year  
     - BIC vente: 1 trimestre per ~4,208€ CA, max 4/year
   - Pension formula: `salaire annuel moyen * taux * (trimestres validés / trimestres requis)`
   - SAM = average of best 25 years of annual income (capped at PASS)
   - Taux plein = 50% (at 67 or with enough trimestres)
   - Trimestres requis = 172 (born 1986)

   **Retraite complémentaire (CIPAV / RCI):**
   - Points acquired per year based on CA bracket
   - Value per point at retirement × total points

   **Simplified estimation approach** (recommended for MVP):
   ```python
   def estimate_monthly_pension(
       birth_year: int,
       activity_type: str,
       ca_history: list[Decimal],  # Annual CA for each year of career
       retirement_age: int,
   ) -> dict:
       """
       Returns {
           "base_monthly": Decimal,
           "complementaire_monthly": Decimal, 
           "total_monthly": Decimal,
           "trimestres_valides": int,
           "trimestres_requis": int,
           "taux": Decimal,  # 50% at taux plein, less with décote
           "confidence": str,  # "low" | "medium" — never "high", we're estimating
       }
       """
   ```

2. **Constants to encode:**
   ```python
   # Trimestre validation thresholds (2024, inflation-adjusted)
   TRIMESTRE_THRESHOLDS = {
       "bnc_non_reglementee": Decimal("2880"),
       "bic_services": Decimal("2540"),
       "bic_vente": Decimal("4208"),
       "bnc_cipav": Decimal("2880"),
   }
   
   # PASS (Plafond Annuel de la Sécurité Sociale) - 2024 value
   PASS_2024 = Decimal("46368")
   
   # Trimestres requis by birth year
   TRIMESTRES_REQUIS = {
       1986: 172,  # Born 1986 → needs 172 trimestres for taux plein
       # Add a lookup function for other years
   }
   
   # Taux plein at age 67 regardless of trimestres
   AGE_TAUX_PLEIN_AUTO = 67
   ```

3. **Integration with projection engine:**
   - The projection engine already computes `gross_annual` for each year
   - Pass the CA history to `estimate_monthly_pension()` at the retirement year
   - Add `pension_monthly` to `YearProjection` for post-retirement years
   - Include in the retirement income calculation

4. **API endpoint:**
   - `GET /api/projection/pension-estimate` — returns the pension estimate based on current profile and projected CA
   - Used by the Runway page to display pension info

### Frontend

5. **Display on Runway page:**
   - New card or section: "Retraite estimée"
   - Show: base + complémentaire = total mensuel
   - Show: trimestres validés / requis, taux appliqué
   - Caveat text: "Estimation indicative basée sur votre CA projeté. Consultez info-retraite.fr pour un calcul officiel."
   - Link to info-retraite.fr

6. **Include in post-retirement income** (TASK-5.2):
   - Pension becomes part of monthly income after retirement
   - Visible in the projection table "Pension" column
   - Reduces the gap between expenses and income

## Acceptance Criteria

- [ ] Pension estimation computes trimestres from CA history
- [ ] Décote applied if trimestres < required and age < 67
- [ ] Taux plein applied at age 67 regardless of trimestres
- [ ] Monthly estimate in reasonable range (500–1,500€ for typical AE)
- [ ] Confidence label shown ("estimation indicative")
- [ ] Integrated into projection timeline for post-retirement years
- [ ] Unit tests with at least 3 scenarios:
  - Full career AE at 5,600€/month → ~X trimestres, ~Y€/month
  - Late-start AE (only 15 years of contributions) → fewer trimestres, décote
  - High-CA AE hitting PASS ceiling
- [ ] LEARNINGS.md updated

## Notes

- The AE pension system is genuinely complex. For MVP, err on the side of conservative estimates (slightly underestimate pension) — it's better for the user to be pleasantly surprised than to plan on income that doesn't materialize.
- CIPAV vs CNAV regime depends on the activity type. BNC non-réglementée was moved from CIPAV to CNAV in 2018 for new registrations. For simplicity, assume CNAV for all new AE.
- The trimestre threshold amounts inflate annually (tied to SMIC). Use the same inflation rate as the projection engine.
- info-retraite.fr provides exact calculations — always link to it and label our estimate as approximate.
