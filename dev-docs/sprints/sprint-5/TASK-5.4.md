# TASK-5.4: Actionable Insights Engine

**Status:** TODO
**Sprint:** 5
**Priority:** P0 (critical — transforms the app from "calculator" to "advisor")
**Est. effort:** 3 hr
**Dependencies:** TASK-4.1

## Context

The projection engine computes a complete 30-year (soon 55-year with TASK-5.2) timeline. It has all the data needed to answer the user's real questions: "Am I on track?", "What should I change?", "What matters most?" — but currently it just dumps a table and two charts. The user is left to stare at numbers and figure it out themselves.

This task builds an insights engine that analyzes the projection and produces ranked, actionable recommendations. Not generic tips ("save more!") — specific, quantified advice based on the user's actual situation.

## Requirements

### Backend: Insights Engine

1. **Create `backend/app/calculations/insights.py`**:

   ```python
   @dataclass
   class Insight:
       id: str                    # e.g. "increase_savings_rate"
       category: str              # "savings" | "income" | "expenses" | "structure" | "allocation"
       severity: str              # "critical" | "warning" | "opportunity" | "positive"
       title: str                 # Short headline (i18n key)
       description: str           # Explanation with specific numbers
       impact_monthly: Decimal    # Estimated monthly impact at retirement
       impact_wealth: Decimal     # Estimated impact on final wealth
       action: str                # What to do (i18n key)
       priority: int              # 1 = most impactful
   
   def generate_insights(
       projection: list[YearProjection],
       summary: ProjectionSummary,
       profile: ProjectionInput,
   ) -> list[Insight]:
   ```

2. **Insight rules to implement** (ranked by typical impact):

   **Critical (red) — retirement is at risk:**
   - `wealth_exhaustion`: Wealth runs out before age 90 → "Votre patrimoine s'épuise à {age} ans. Augmentez votre épargne de {X}€/mois pour tenir jusqu'à 95 ans."
   - `no_goal_reached`: Goal never reached → "Votre objectif de {goal}€/mois n'est pas atteint. Il faudrait {X}€/mois d'épargne supplémentaire."
   - `negative_net`: Net income goes negative in any year → "Vos dépenses dépassent vos revenus en {year}. Vérifiez vos charges."

   **Warning (amber) — sub-optimal but not critical:**
   - `low_savings_rate`: Savings < 15% of net income → "Vous épargnez {X}% de votre net. Viser 20% ajouterait {Y}k€ à votre patrimoine."
   - `savings_allocation_unbalanced`: >80% in Livret A/LDDS → "Votre épargne est concentrée sur des supports à faible rendement. Diversifier vers AV UC ou PEA pourrait ajouter {X}k€."
   - `livret_a_near_ceiling`: Balance approaching 22,950€ → "Votre Livret A approche du plafond. Redirigez les versements vers un support plus rentable."
   - `no_per_contribution`: PER = 0 while marginal tax rate is high → "Le PER offre une déduction fiscale immédiate. {X}€/mois sur PER vous ferait économiser {Y}€/an d'impôts."
   - `status_change_beneficial`: SASU net > AE net at projected CA → "À votre CA projeté de {X}€ en {year}, passer en SASU économiserait {Y}€/an."

   **Opportunity (teal) — things that could improve:**
   - `increase_ca_growth`: Switching from "prudent" to "modéré" growth → "Passer de 1% à 3% de croissance annuelle ajouterait {X}k€ à votre patrimoine."
   - `one_more_year`: Working to 71 instead of 70 → "Une année de plus ajoute {X}k€ au patrimoine et réduit la période de retrait de 1 an."
   - `marriage_impact`: Wedding event impacts runway → "Votre mariage en {year} réduit temporairement votre épargne de {X} mois."
   - `kid_peak_cost_year`: Year when kid costs peak → "Les coûts enfants atteignent {X}€/mois en {year} (lycée + activités). Anticipez."

   **Positive (emerald) — things going well:**
   - `goal_reached_early`: Goal reached before retirement → "Félicitations ! Votre objectif est atteint dès {year} ({age} ans)."
   - `wealth_milestone_soon`: Next milestone within 3 years → "Vous atteindrez {milestone}€ de patrimoine en {year}."
   - `good_savings_rate`: Savings > 25% of net → "Excellent taux d'épargne de {X}%. Vous êtes sur la bonne voie."
   - `diversified_allocation`: Investments spread across 3+ vehicles → "Allocation bien diversifiée."

3. **Impact estimation logic:**
   
   For each insight, compute the actual impact by running a mini "what-if" projection:
   ```python
   # Example: "increase savings by 200€/month"
   modified_input = copy(profile)
   modified_input.allocations["pea"]["monthly"] += Decimal("200")
   modified_projection = project_timeline(modified_input, scale)
   delta_wealth = modified_projection[-1].total_wealth - projection[-1].total_wealth
   # → "Ajouter 200€/mois sur PEA ajouterait 127k€ à votre patrimoine à 70 ans"
   ```

   For MVP, use analytical approximations instead of re-running the full engine:
   ```python
   # Approximate: additional_monthly * 12 * years * (1 + avg_return)^(years/2)
   ```

4. **Ranking:** Sort insights by `abs(impact_wealth)` descending. Return top 5.

### API

5. **Extend `/api/projection` response** to include an `insights` array:
   ```json
   {
     "timeline": [...],
     "summary": {...},
     "insights": [
       {
         "id": "low_savings_rate",
         "severity": "warning",
         "title": "Taux d'épargne faible",
         "description": "Vous épargnez 13% de votre net. Viser 20% ajouterait 47k€ à votre patrimoine.",
         "impact_wealth": 47000,
         "action": "Augmentez vos versements mensuels dans Épargne",
         "priority": 1
       }
     ]
   }
   ```

### Frontend

6. **Create `InsightCards.svelte`** component:
   - Render as a list of cards below the projection table
   - Color-coded by severity: rose (critical), amber (warning), teal (opportunity), emerald (positive)
   - Each card: icon + title + description + suggested action
   - Critical insights get a larger, more prominent card style
   - Max 5 insights displayed (most impactful first)

7. **Integration:** Add to Runway page between milestones and the table (or after the table as a "Recommandations" section).

## Acceptance Criteria

- [ ] At least 8 insight rules implemented
- [ ] Insights ranked by impact magnitude
- [ ] Each insight includes specific numbers from the user's actual projection
- [ ] Critical insights trigger when wealth runs out or goal is unreachable
- [ ] At least one positive insight shows when the user is on track
- [ ] Frontend renders insight cards with correct color coding
- [ ] Insights update when scale changes
- [ ] Unit tests for each insight rule with edge cases
- [ ] LEARNINGS.md updated

## Notes

- The power of this feature is specificity. "Save more" is useless. "Adding 200€/mois on PEA adds 127k€ to your patrimoine at 70" changes behavior. Every insight must include a number.
- Don't overwhelm — max 5 insights, most impactful first. If everything is fine, show 2-3 positive reinforcements.
- The insight text should be in i18n keys with interpolation variables, not hardcoded French strings.
- Consider making insights clickable — tapping "Augmentez vos versements" could navigate to the Épargne section.
