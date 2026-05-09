# TASK-5.7: Scenario Comparison Mode

**Status:** TODO
**Sprint:** 5
**Priority:** P1 (high)
**Est. effort:** 3 hr
**Dependencies:** TASK-4.2

## Context

The most common thing a user wants to do after seeing their projection is ask "what if?" — What if I save 1,000€/month instead of 750€? What if I delay retirement to 72? What if I don't buy the house? Currently, testing these requires navigating to the relevant section, changing a value, going back to Runway, and trying to remember the original numbers. This friction kills exploration.

A scenario comparison mode lets the user fork their current plan, tweak key parameters, and see both projections side-by-side — without modifying their actual saved data.

## Requirements

### Backend

1. **Add scenario endpoint** `POST /api/projection/compare`:
   ```json
   {
     "base_scale": "moderate",
     "overrides": {
       "monthly_savings": 1000,           // Override total monthly savings
       "target_retirement_age": 72,       // Override retirement age
       "growth_rate": 0.03,               // Override CA growth rate
       "monthly_expenses_delta": -500,    // Reduce expenses by 500€
       "disable_project": "uuid-xxx",     // Exclude a specific project
       "extra_monthly_investment": {       // Add to a specific vehicle
         "vehicle_key": "pea",
         "amount": 200
       }
     }
   }
   ```
   
   Response:
   ```json
   {
     "base": { "timeline": [...], "summary": {...} },
     "scenario": { "timeline": [...], "summary": {...} },
     "delta": {
       "final_wealth": "+87,400€",
       "passive_monthly": "+291€",
       "goal_reached_year_delta": "-4 ans",
       "wealth_exhaustion_delta": "+8 ans"
     }
   }
   ```

2. **Implementation approach:**
   - The projection engine is already a pure function (`project_timeline(input, scale)`)
   - Clone the `ProjectionInput`, apply overrides, run the engine twice
   - Compute deltas on the summary fields
   - Return both timelines for chart overlay

### Frontend

3. **"Et si...?" button** on the Runway page:
   - Positioned near the top, below the readiness score
   - Opens a slide-over panel or modal with scenario controls
   - Doesn't navigate away from the Runway page

4. **Scenario controls panel** — quick-adjust sliders/inputs for the most impactful parameters:
   
   | Parameter | Control | Range | Step |
   |-----------|---------|-------|------|
   | Épargne mensuelle | Slider + input | 0 → 3,000€ | 50€ |
   | Âge de retraite | Slider + input | 55 → 80 | 1 |
   | Croissance CA | Preset buttons | 0% / 1% / 3% / 6% | — |
   | Dépenses mensuelles | Slider | -1,000€ → +1,000€ delta | 100€ |
   
   Each control shows the current (base) value and the scenario value.
   Controls update the scenario projection in real-time (debounced 500ms).

5. **Side-by-side display** when scenario is active:
   - Hero stats show base → scenario with delta: "163.9k€ → 251.3k€ (+87.4k€)"
   - Wealth chart overlays both curves: base in zinc-600 (faded), scenario in teal
   - Key deltas highlighted: "Retraite 4 ans plus tôt", "Patrimoine +53%"

6. **"Appliquer ce scénario" button:**
   - If the user likes a scenario, they can apply it — this updates their actual saved data
   - Confirm dialog: "Cela modifiera vos paramètres sauvegardés. Continuer ?"
   - After applying, the scenario panel closes and Runway shows the new base projection

7. **"Réinitialiser" button** to clear the scenario and return to base view.

### Predefined Scenarios (quick-start)

8. **Offer 3 preset scenarios** at the top of the panel:
   - "💪 Effort maximum" — savings +50%, expenses -10%, growth ambitious
   - "🏖️ Retraite anticipée" — retirement age -5 years, same savings
   - "🏠 Sans le projet immobilier" — disable the investment project
   
   Tapping a preset fills the controls; the user can still adjust.

## Acceptance Criteria

- [ ] Compare endpoint returns base and scenario projections with deltas
- [ ] Scenario panel opens without navigating away from Runway
- [ ] At least 4 adjustable parameters (savings, retirement age, growth, expenses)
- [ ] Chart overlays both curves with clear visual distinction
- [ ] Hero stats show base vs scenario with colored deltas
- [ ] Real-time updates on parameter change (debounced)
- [ ] "Appliquer" saves scenario values to the user's profile
- [ ] "Réinitialiser" clears the scenario view
- [ ] Predefined scenarios load with correct overrides
- [ ] Performance: scenario re-computation < 300ms
- [ ] LEARNINGS.md updated

## Notes

- The compare endpoint runs the engine twice, which doubles computation time. Since the engine targets < 500ms, this should be < 1s total — acceptable for an interactive feature. If it's too slow, consider computing only every 5th year for the scenario preview.
- The scenario panel should feel lightweight — not a full configuration screen. It's "quick tweaks," not "rebuild your plan." Deep changes still happen in the dedicated sections.
- The overlay chart is the money shot of this feature. Two curves, one faded, one bright, with the gap between them visually communicating the impact of the change. Consider filling the delta area with a subtle green (if scenario is better) or red (if worse).
- Mobile: the scenario panel should be a bottom sheet, not a side panel. Controls stack vertically.
