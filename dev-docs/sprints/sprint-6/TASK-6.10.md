# TASK-6.10: Projection Explainer — Year Drill-Down

**Status:** TODO
**Sprint:** 6
**Priority:** P2 (medium — UX polish)
**Est. effort:** 2 hr
**Dependencies:** TASK-5.6

## Context

The projection table shows every 5th year with 11 columns of numbers. A user seeing that their net drops from +15k in 2034 to -22k in 2036 has no idea why. Was it a car replacement? All three kids in school simultaneously? A renovation project? The table is data-rich but explanation-poor.

A year drill-down lets the user click on any row in the projection table (or any point on the chart) and see the complete breakdown for that year: every income source, every expense line, every life entity cost event that fired, every investment contribution and return.

## Requirements

### Backend

1. **Endpoint `GET /api/projection/year/{year}?scale=moderate`:**
   ```json
   {
     "year": 2036,
     "age": 50,
     "phase": "accumulation",

     "income": {
       "gross_ca": 120345,
       "growth_rate_applied": "6.0%",
       "caf": 4707,
       "cesu_credit": 1026,
       "charity_credit": 0,
       "project_income": 0,
       "pension": 0,
       "total": 126078
     },

     "charges": {
       "ae_cotisations": 35502,
       "ae_rate": "29.5%",
       "cfe": 359,
       "total": 35861
     },

     "expenses": {
       "base": {
         "loyer": 6000,
         "alimentation": 18000,
         "transport": 2880,
         "...": "..."
       },
       "base_total_monthly": 4513,
       "base_total_annual": 54197,
       "inflation_factor": "1.159 (2.0%/an × 10 ans)"
     },

     "life_entities": [
       {
         "name": "Saoirse",
         "type": "kid",
         "age": 18,
         "events_active": [
           { "label": "Cantine lycée", "amount": 150, "frequency": "monthly", "annual": 1800 },
           { "label": "Fournitures lycée", "amount": 600, "frequency": "annual", "annual": 600 },
           { "label": "Camp d'été", "amount": 800, "frequency": "annual", "annual": 800 },
           { "label": "Activités extra", "amount": 100, "frequency": "monthly", "annual": 1200 },
           { "label": "Permis de conduire", "amount": 1800, "frequency": "once", "annual": 1800 },
           { "label": "Première voiture", "amount": 5000, "frequency": "once", "annual": 5000 }
         ],
         "subtotal": 11200,
         "note": "Année du permis et de la première voiture"
       },
       {
         "name": "Ellie",
         "type": "kid",
         "age": 14,
         "events_active": [
           { "label": "Cantine collège", "amount": 150, "frequency": "monthly", "annual": 1800 },
           { "label": "Fournitures collège", "amount": 400, "frequency": "annual", "annual": 400 },
           { "label": "Camp d'été", "amount": 800, "frequency": "annual", "annual": 800 },
           { "label": "Activités extra", "amount": 100, "frequency": "monthly", "annual": 1200 }
         ],
         "subtotal": 4200
       },
       {
         "name": "Romy",
         "type": "kid",
         "age": 11,
         "events_active": [ "..." ],
         "subtotal": 4600
       },
       {
         "name": "Layla",
         "type": "pet",
         "age": 11,
         "events_active": [
           { "label": "Nourriture", "annual": 600 },
           { "label": "Vétérinaire annuel", "annual": 200 },
           { "label": "Toilettage", "annual": 300 },
           { "label": "Soins renforcés (vieillesse)", "annual": 400 },
           { "label": "Rappel vaccins", "annual": 80 }
         ],
         "subtotal": 1580,
         "note": "Soins renforcés actifs (âge > 10)"
       }
     ],

     "life_entities_total": {
       "kids": 20000,
       "pets": 1580,
       "cars": 0,
       "tech": 3108,
       "total": 24688
     },

     "loans": [
       { "label": "Crédit immobilier", "monthly": 500, "annual": 6000, "status": "active", "ends": "2035-03" }
     ],

     "investments": {
       "contributions": { "livret_a": 6000, "av_euro": 3000, "total": 9000 },
       "returns": { "livret_a": 573, "av_euro": 564, "total": 1137 },
       "balances": { "livret_a": 22950, "av_euro": 84821, "total": 107771 },
       "notes": ["Livret A at ceiling — overflow redirected to AV euro"]
     },

     "summary": {
       "total_income": 126078,
       "total_outgoing": 127087,
       "net": -1009,
       "net_status": "deficit",
       "explanation": "Année chargée : permis + voiture de Saoirse (6 800€), trois enfants à charge simultanément, Layla en soins renforcés. Le net est légèrement déficitaire (-84€/mois)."
     }
   }
   ```

2. **Auto-generate explanation text:**
   - Identify the 2-3 largest expense drivers for the year
   - Note any one-time events (car replacement, wedding, permis)
   - Note any new phase transitions (kid entering collège, pet entering old age)
   - Produce a 1-2 sentence natural language summary

### Frontend

3. **Click-to-expand on projection table:**
   - Each row in the projection table becomes clickable
   - Clicking opens an expanded detail view below the row (accordion style)
   - Shows the full breakdown from the API response
   - Grouped by category: Income | Charges | Expenses | Life Entities | Loans | Investments

4. **Click-on-chart integration:**
   - Clicking a point on the wealth or income chart opens the drill-down for that year
   - Reuses the same expanded view component

5. **Visual breakdown:**
   - Mini donut chart showing expense distribution for that year
   - Life entity cards showing which entities are active and what they cost
   - "Why this year?" callout box with the auto-generated explanation

## Acceptance Criteria

- [ ] Drill-down endpoint returns complete year breakdown
- [ ] Every income source itemized
- [ ] Every expense category itemized (base + life entities + loans)
- [ ] Every active life entity listed with its active cost events
- [ ] Investment contributions, returns, and balances per vehicle
- [ ] Auto-generated explanation identifies key drivers
- [ ] Frontend expandable row works on table click
- [ ] Chart click opens the same drill-down
- [ ] Performance: drill-down data extracted from cached projection (no re-computation)
- [ ] LEARNINGS.md updated

## Notes

- This is the feature that makes the projection debuggable. When a user sees a spike or dip, they need to understand *why*. Without the drill-down, they're left guessing. With it, every number is traceable to a specific input.
- The auto-generated explanation is a nice touch but don't over-engineer it. A simple template-based approach works: "Année chargée : {top_expense_1} ({amount}€), {top_expense_2} ({amount}€). {n} enfants à charge."
- Performance: the drill-down data is a subset of the full projection. Don't re-run the engine — extract from the cached timeline. Add the entity-level detail to the YearProjection dataclass (or compute it on demand from the stored input).
