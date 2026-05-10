# TASK-6.8: Disposable Income Waterfall

**Status:** TODO
**Sprint:** 6
**Priority:** P1 (high)
**Est. effort:** 2 hr
**Dependencies:** None

## Context

The user enters CA, charges, expenses, life costs, and savings across 5 different sections. But nowhere does the app show how these all fit together — the flow from gross income to actual savings. The waterfall visualization answers: "Where does my money go every month?"

For Richard in 2026: 5,600€ gross → -1,467€ charges → 4,133€ net → -3,705€ expenses → -933€ kids → -98€ pet → -25€ tech → -750€ savings = **-845€ deficit**. Seeing this as a single flowing diagram makes the deficit visceral and immediately actionable.

## Requirements

### Backend

1. **Endpoint `GET /api/profile/waterfall`:**
   ```json
   {
     "year": 2026,
     "monthly": {
       "gross_ca": 5600,
       "charges": -1467,
       "cfe_monthly": -25,
       "net_after_charges": 4108,
       "base_expenses": -3705,
       "loan_payments": -590,
       "kid_costs": -933,
       "pet_costs": -98,
       "car_costs": -183,
       "tech_costs": -25,
       "recurring_costs": 0,
       "caf_income": 338,
       "tax_credits": 72,
       "disposable": -1016,
       "savings_planned": -750,
       "monthly_surplus_deficit": -1766
     },
     "annual": { ... },
     "status": "deficit",
     "deficit_note": "Vos dépenses dépassent vos revenus de 1 016€/mois avant épargne. Assurez-vous d'avoir des réserves pour couvrir ce déficit."
   }
   ```

### Frontend

2. **Waterfall chart** (SVG, following the Visualizer design system):
   - Vertical bars flowing left to right (or top to bottom)
   - Green bars: income (CA, CAF, tax credits)
   - Red bars: deductions (charges, expenses, life costs, loans)
   - Teal bar: savings
   - Running total line connecting the bars
   - Final bar: surplus (emerald) or deficit (rose)

3. **Placement:** New card on the Revenus page or a dedicated "Vue d'ensemble" at the top of the app. This is the "dashboard" view that ties everything together.

4. **Interactive:** Hover over any bar to see the breakdown and the corresponding source section. Click to navigate to that section.

5. **Responsive text summary:**
   - Surplus: "Il vous reste {X}€/mois après charges, dépenses et épargne. Vous pouvez augmenter votre épargne ou constituer un fonds d'urgence."
   - Deficit: "Vos dépenses dépassent vos revenus de {X}€/mois. Vérifiez vos charges ou augmentez votre CA."
   - Breakeven: "Votre budget est à l'équilibre. Pas de marge pour l'imprévu."

## Acceptance Criteria

- [ ] Waterfall endpoint returns correct monthly breakdown
- [ ] All income and expense sources included
- [ ] Waterfall chart renders with correct proportions
- [ ] Surplus shown in emerald, deficit in rose
- [ ] Hovering shows breakdown per bar
- [ ] Deficit note displayed when expenses > income
- [ ] Values match projection year 0 data
- [ ] LEARNINGS.md updated

## Notes

- The waterfall might be the single most useful "aha" moment in the app. Most freelancers have never seen their money flow laid out this clearly. The fact that Richard is running a ~1,000€/month deficit before savings makes the 9,000€/year investment contribution look problematic — where's that money coming from?
- Consider adding a "projected waterfall" toggle that shows the waterfall for year 5, 10, 15 — so the user can see how the flow evolves as CA grows and loans end.
