# TASK-6.6: Expense Evolution Timeline

**Status:** DONE (backend + tests, 2026-05-09)
**Sprint:** 6
**Priority:** P1 (high)
**Est. effort:** 2 hr
**Dependencies:** TASK-6.3

## Context

Expenses aren't static. The current model treats base_expenses as a flat 3,705€/month inflated uniformly. But in reality, major components change at specific moments: the mortgage ends in 2035 (-590€/mois), kids leave home between 2039–2048 (progressive expense drop), the dog passes around 2038 (-100€/mois), cars need periodic replacement spikes.

The engine already computes kid/pet/car/tech costs dynamically via lifecycle events, and Task 6.3 adds loan termination. But the user has no way to *see* how their total expenses evolve over time. They enter 3,705€ and assume it stays roughly there. In reality, their monthly expenses might go: 3,705€ (2026) → 3,115€ (2035, mortgage ends) → 2,600€ (2042, kids independent) → 2,200€ (2050, minimal). That 1,500€/month swing over the projection period is the difference between "wealth exhaustion at 72" and "comfortable retirement."

## Requirements

### Backend

1. **New endpoint `GET /api/projection/expense-timeline`:**
   - Returns year-by-year expense breakdown from the projection:
   ```json
   {
     "timeline": [
       {
         "year": 2026,
         "age": 40,
         "base_expenses": 3705,
         "loan_payments": 590,
         "kid_expenses_monthly": 933,
         "pet_expenses_monthly": 98,
         "car_expenses_monthly": 183,
         "tech_expenses_monthly": 25,
         "recurring_monthly": 0,
         "project_expenses_monthly": 0,
         "total_monthly": 5534,
         "events": ["3 enfants à charge", "Crédit immobilier actif"]
       },
       {
         "year": 2035,
         "age": 49,
         "base_expenses": 3705,
         "loan_payments": 0,
         "total_monthly": 4200,
         "events": ["✅ Crédit immobilier terminé (-590€/mois)"],
         "delta_vs_previous": -590
       }
     ],
     "key_events": [
       { "year": 2028, "event": "Prêt auto terminé", "impact": -90 },
       { "year": 2035, "event": "Crédit immobilier terminé", "impact": -500 },
       { "year": 2039, "event": "Saoirse indépendante", "impact": -300 },
       { "year": 2042, "event": "Ellie indépendante", "impact": -300 },
       { "year": 2048, "event": "Romy indépendante", "impact": -350 },
       { "year": 2038, "event": "Layla (fin de vie estimée)", "impact": -100 }
     ]
   }
   ```

2. **Extract expense events from projection data:**
   - Detect loan terminations (from loans model)
   - Detect kid cost phase transitions (last cost event ending = "independence")
   - Detect pet end-of-life (last cost event)
   - Detect car replacement years (large one-time spike)

### Frontend

3. **Expense evolution chart** on the Charges page (or Runway page):
   - Stacked area chart showing expense categories over time
   - Colors: base expenses (zinc), loans (amber), kids (purple), pets (rose), cars (sky), tech (teal)
   - Key events marked with vertical dotted lines and labels
   - Hover tooltip showing monthly breakdown for that year

4. **"Événements à venir" card** on the Charges page:
   - Chronological list of upcoming expense changes
   - Each event: year, description, monthly impact (green for decrease, red for increase)
   - "Your expenses drop from 5,534€/mois to 2,200€/mois by 2050"

5. **Integration with insights engine:**
   - "Quand votre crédit immobilier se termine en 2035, redirigez les 500€/mois vers votre PEA"
   - "Vos dépenses enfants atteignent un pic de X€/mois en 2036 (lycée × 2 + études), puis diminuent"

## Acceptance Criteria

- [ ] Expense timeline endpoint returns year-by-year breakdown
- [ ] Key events detected automatically (loan ends, kid independence, pet EOL)
- [ ] Stacked area chart renders expense evolution over 30 years
- [ ] Event markers on chart with labels
- [ ] "Événements à venir" card lists upcoming changes chronologically
- [ ] Monthly impact shown for each event (positive/negative)
- [ ] LEARNINGS.md updated

## Notes

- This visualization might be the most eye-opening feature in the app. Seeing expenses drop from 5,500 to 2,200 over 24 years reframes the entire retirement conversation. The user doesn't need 5,500€/month at 70 — they need ~2,200€/month (plus inflation). That's a completely different savings target.
- The stacked area chart should clearly show the "layers peeling off" — the mortgage layer disappears in 2035, kid layers shrink progressively through the 2040s, etc.
