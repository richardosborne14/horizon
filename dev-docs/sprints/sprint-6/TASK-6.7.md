# TASK-6.7: Sensitivity Analysis Engine

**Status:** TODO
**Sprint:** 6
**Priority:** P1 (high)
**Est. effort:** 3 hr
**Dependencies:** TASK-5.4

## Context

Users look at a projection and ask "what matters most?" Is it the savings rate? The growth rate? The investment allocation? The retirement age? Currently they can only find out by manually changing parameters one at a time and comparing results. A sensitivity analysis does this systematically — nudge each parameter, measure the impact, and rank them.

This tells the user where to focus their energy. If increasing savings by 200€/month adds 80k€ to final wealth but switching from Livret A to PEA adds 120k€, the allocation change is the higher-leverage move. Most users would intuitively focus on "save more" when "invest smarter" actually matters more.

## Requirements

### Backend

1. **Create `backend/app/calculations/sensitivity.py`:**

   ```python
   @dataclass
   class SensitivityResult:
       parameter: str           # "monthly_savings", "growth_rate", etc.
       label: str               # "Épargne mensuelle"
       base_value: str          # "750€/mois"
       test_value: str          # "950€/mois (+200€)"
       base_wealth: Decimal     # Wealth at retirement (base scenario)
       test_wealth: Decimal     # Wealth at retirement (modified scenario)
       delta_wealth: Decimal    # Difference
       delta_pct: Decimal       # % change
       delta_exhaustion: int    # Change in wealth exhaustion age (years)
       rank: int                # 1 = most impactful

   def run_sensitivity_analysis(
       inp: ProjectionInput,
       scale: str,
   ) -> list[SensitivityResult]:
   ```

2. **Parameters to test** (each nudged by a meaningful amount):

   | Parameter | Nudge | What it means |
   |-----------|-------|---------------|
   | Monthly savings | +200€/mois | Save more |
   | Savings allocation | Move 50% from Livret A → PEA | Invest smarter |
   | Growth rate | +2% (e.g., 6% → 8%) | Earn more |
   | Retirement age | +2 years | Work longer |
   | Monthly expenses | -300€/mois | Spend less |
   | Loan freed (if applicable) | Redirect loan payment to savings on termination | Reallocate on loan end |
   | Status change | Switch to SASU at optimal year | Change legal structure |

3. **Implementation approach:**
   - For each parameter, clone the `ProjectionInput`, apply the nudge, run the full projection
   - Compare final wealth, wealth exhaustion age, and goal achievement
   - Rank by absolute delta_wealth descending
   - Return top 7 results

4. **Performance:** 7 projection runs × ~100ms each = ~700ms. Acceptable. Cache the result for 30 seconds (invalidate on profile change, same as main projection).

### API

5. **Endpoint `GET /api/projection/sensitivity?scale=moderate`:**
   ```json
   {
     "base_wealth_at_retirement": 313274,
     "base_exhaustion_age": 72,
     "parameters": [
       {
         "parameter": "savings_to_pea",
         "label": "Rediriger 375€/mois vers PEA",
         "base_value": "PEA: 0€/mois",
         "test_value": "PEA: 375€/mois (50% de l'épargne)",
         "delta_wealth": 127400,
         "delta_pct": 40.6,
         "delta_exhaustion": 6,
         "rank": 1
       },
       {
         "parameter": "retirement_age",
         "label": "Travailler 2 ans de plus (→ 72 ans)",
         "delta_wealth": 89000,
         "delta_exhaustion": 4,
         "rank": 2
       },
       {
         "parameter": "monthly_savings",
         "label": "Épargner 200€/mois de plus",
         "delta_wealth": 72000,
         "delta_exhaustion": 3,
         "rank": 3
       },
       ...
     ]
   }
   ```

### Frontend

6. **Sensitivity chart** on Runway page (new section: "Qu'est-ce qui compte le plus ?"):
   - Horizontal bar chart ranking parameters by impact
   - Each bar: parameter label on the left, delta wealth on the right
   - Color: teal for positive impact, rose for negative
   - Clicking a bar could open the scenario comparison (Task 5.7) with that parameter pre-loaded

7. **Narrative summary:**
   - "Le levier le plus puissant est votre allocation d'épargne. Rediriger la moitié de vos versements vers un PEA ajouterait 127k€ à votre patrimoine — plus que toute autre action individuelle."

## Acceptance Criteria

- [ ] At least 6 parameters tested
- [ ] Parameters ranked by absolute impact on final wealth
- [ ] Results include delta_wealth, delta_pct, and delta_exhaustion
- [ ] Performance < 1 second for full analysis
- [ ] Frontend renders horizontal bar chart with ranking
- [ ] Narrative summary generated for the top lever
- [ ] Results cached and invalidated on profile changes
- [ ] Unit tests for each parameter nudge
- [ ] LEARNINGS.md updated

## Notes

- The sensitivity analysis is computational — it re-runs the projection 7 times. But since each run is ~100ms, the total is under a second. If performance becomes an issue, use approximate formulas instead of full reruns (but full reruns are more accurate).
- The ranking often surprises users. Most people think "save more" is the top lever. But for someone already saving 750€/month, the marginal value of +200€ is less than reallocating what they already save from 2.5% vehicles to 7% vehicles. The compounding effect over 30 years makes allocation the dominant factor.
- This feature creates natural upsell moments: "Your biggest lever is investment allocation, but you're only using 2 of 7 vehicles. Explore your options in Épargne →"
