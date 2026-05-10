# TASK-6.2: Pension Engine v2 (Career-Aware)

**Status:** TODO
**Sprint:** 6
**Priority:** P0 (critical — the accuracy leap)
**Est. effort:** 3 hr
**Dependencies:** TASK-6.1, TASK-5.3

## Context

Task 5.3 built a basic pension estimation from projected AE income alone. This task upgrades it to use the full career history — past CDI/CDD periods, unemployment gaps, parental leave — to compute a much more accurate pension estimate.

The difference is enormous. A freelancer who had 8 years of CDI at 40k€/year has 32 trimestres already banked at a much higher salary base than their current AE income. Their pension from the regime général portion alone could be 400–700€/month. Add the AE portion on top, and the post-retirement picture changes from "wealth exhaustion at 72" to potentially "tight but viable."

## Requirements

### Pension Calculation — Full Model

1. **Extend `backend/app/calculations/pension.py`** to accept career history:

   ```python
   @dataclass
   class PensionInput:
       birth_year: int
       career_periods: list[dict]      # From career history API
       projected_ae_ca: list[Decimal]   # Future AE annual CA per year
       activity_type: str               # Current AE type
       retirement_age: int
       current_year: int

   @dataclass
   class PensionEstimate:
       # Trimestres
       trimestres_salarie: int          # From CDI/CDD/SASU periods
       trimestres_ae: int               # From AE periods (past + projected)
       trimestres_other: int            # Unemployment, parental, etc.
       trimestres_total: int
       trimestres_required: int         # For taux plein (depends on birth year)
       has_taux_plein: bool

       # Pension amounts
       base_salarie_monthly: Decimal    # Retraite de base from regime général
       base_ae_monthly: Decimal         # Retraite de base from AE
       complementaire_monthly: Decimal  # Retraite complémentaire (AGIRC-ARRCO + RCI)
       total_monthly: Decimal

       # Metadata
       sam_salarie: Decimal             # Salaire Annuel Moyen (best 25 years, regime général)
       sam_ae: Decimal                  # Equivalent for AE
       taux: Decimal                    # Applied rate (50% at taux plein, less with décote)
       decote_trimestres: int           # Trimestres missing for taux plein
       decote_pct: Decimal              # Percentage reduction
       confidence: str                  # "low" | "medium"
   ```

### Regime Général (CDI/CDD/SASU) Pension

2. **Trimestre validation from salaried work:**
   - 1 trimestre per 150 × SMIC horaire brut of annual salary
   - 2024 SMIC horaire = 11.65€ → threshold = 1,747.50€/trimestre → 6,990€/year for 4 trimestres
   - Full-time CDI at 35k€+ = 4 trimestres/year automatically
   - Part-time: proportional (80% time at 40k = 32k → still 4 trimestres)
   - Max 4 per year regardless of salary

3. **SAM (Salaire Annuel Moyen) calculation:**
   ```python
   # Take all annual salaries from salaried work
   # Cap each at PASS (Plafond Annuel de la Sécurité Sociale)
   # PASS 2024 = 46,368€, inflate for future years
   # Take the best 25 years (for people born after 1953)
   # Average them → SAM
   
   capped_salaries = [min(salary, pass_for_year) for salary, year in career]
   best_25 = sorted(capped_salaries, reverse=True)[:25]
   sam = sum(best_25) / min(25, len(best_25))
   ```

4. **Base pension formula:**
   ```python
   # Pension de base = SAM × Taux × (trimestres validés / trimestres requis)
   # Taux plein = 50%
   # With décote: taux = 50% - (0.625% × trimestres manquants)
   #   max décote = 20 trimestres → min taux = 37.5%
   # At age 67: taux plein automatic regardless of trimestres

   if retirement_age >= 67:
       taux = Decimal("0.50")
   elif trimestres_total >= trimestres_required:
       taux = Decimal("0.50")
   else:
       missing = min(trimestres_required - trimestres_total, 20)
       # Also limited by quarters until age 67
       quarters_to_67 = (67 - retirement_age) * 4
       missing = min(missing, quarters_to_67)
       taux = Decimal("0.50") - Decimal("0.00625") * missing

   prorata = min(Decimal("1"), Decimal(str(trimestres_total)) / Decimal(str(trimestres_required)))
   base_monthly = (sam * taux * prorata) / Decimal("12")
   ```

### AE Pension

5. **Trimestre validation from AE:**
   ```python
   # BNC non-réglementée: 1 trimestre per ~2,880€ CA (2024 value)
   # Threshold inflates with SMIC annually
   # Max 4 per year

   TRIMESTRE_THRESHOLDS_2024 = {
       "bnc_non_reglementee": Decimal("2880"),
       "bic_services": Decimal("2540"),
       "bic_vente": Decimal("4208"),
       "bnc_cipav": Decimal("2880"),
   }
   ```

6. **AE base pension:**
   - Similar formula to regime général but with AE-specific SAM
   - AE annual income for SAM = CA × (1 - abattement)
   - BNC abattement = 34% → revenu pris en compte = CA × 0.66
   - This is typically much lower than CDI salary → lower SAM → lower pension

### Complémentaire (AGIRC-ARRCO + RCI)

7. **Simplified complementary pension:**
   ```python
   # Regime général: AGIRC-ARRCO points
   # Points per year ≈ (salary capped at PASS) × cotisation_rate / point_price
   # Cotisation rate ≈ 7.87% (salarié share) on tranche 1
   # Point price 2024 ≈ 19.63€
   # Point value at retirement 2024 ≈ 1.4159€

   points_per_year = (min(salary, pass_value) * Decimal("0.0787")) / Decimal("19.63")
   total_points = sum(points_per_year for year in career)
   complementaire_monthly = (total_points * Decimal("1.4159")) / Decimal("12")
   ```

   For AE: the complémentaire is minimal (RCI regime). Estimate as ~5% of AE base pension.

### Other Period Types

8. **Unemployment (ARE):**
   - 1 trimestre per 50 days of indemnisation
   - Up to 4 trimestres/year
   - No salary contribution to SAM

9. **Parental leave:**
   - Up to 8 trimestres "gratuits" per child (AVPF)
   - These count toward the total but don't affect SAM

10. **Education / foreign / other:**
    - No trimestres unless the user specifies "rachats de trimestres"
    - Foreign periods may count under EU bilateral agreements — too complex for MVP, note as "non comptabilisé"

### Integration with Projection Engine

11. **Compute pension at retirement age:**
    - The projection router assembles career_periods + projected AE CA
    - Passes them to the pension engine
    - Result feeds into post-retirement income (Task 5.2)

12. **Display in pension estimate:**
    ```json
    {
      "pension": {
        "base_salarie": 580,
        "base_ae": 220,
        "complementaire": 180,
        "total_monthly": 980,
        "trimestres": {
          "salarie": 32,
          "ae_past": 24,
          "ae_projected": 80,
          "other": 8,
          "total": 144,
          "required": 172,
          "missing": 28
        },
        "taux": "50.0%",
        "decote": "0%",
        "confidence": "medium",
        "note": "Estimation basée sur votre parcours déclaré. Consultez info-retraite.fr pour un calcul officiel."
      }
    }
    ```

### Frontend

13. **Pension section on Runway page:**
    - Card showing total estimated monthly pension
    - Breakdown: régime général + AE + complémentaire
    - Trimestre progress bar: "144 / 172 trimestres"
    - Note about remaining trimestres needed
    - Link to info-retraite.fr

14. **Impact on readiness score:**
    - Pension income reduces the retirement gap
    - This should significantly improve the readiness score for users with substantial career history

## Acceptance Criteria

- [ ] Pension computes correctly for CDI-only career (no AE)
- [ ] Pension computes correctly for AE-only career (no CDI)
- [ ] Pension computes correctly for mixed career (CDI + AE)
- [ ] SAM uses best 25 years capped at PASS
- [ ] Décote applied correctly when trimestres < required and age < 67
- [ ] Taux plein at 67 regardless of trimestres
- [ ] Complementary pension estimated for regime général
- [ ] Pension feeds into post-retirement projection
- [ ] Frontend shows pension breakdown
- [ ] Readiness score improves when pension is included
- [ ] Hand-verified: 8yr CDI at 40k + 10yr AE at 67k CA → expected pension range
- [ ] Unit tests for each regime type
- [ ] LEARNINGS.md updated

## Notes

- For Richard's case specifically: 8 years CDI (say 2012–2020) at ~35-45k = 32 trimestres + ~400-600€/month base pension from regime général. Plus projected 30 years AE (2020–2056) at growing CA = ~100+ more trimestres. Total ~132+ trimestres vs 172 required. With décote possibly 5-10 trimestres short at 70 → taux ~46-50%. Base pension perhaps 800-1200€/month total. That changes the post-retirement story dramatically.
- Always show "estimation indicative" — we're not an official pension calculator. But being directionally correct is enormously valuable.
- The PASS, SMIC, and point values all inflate over time. Use the same inflation rate as the projection engine for consistency.
