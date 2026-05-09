# TASK-5.5: Retirement Readiness Score

**Status:** TODO
**Sprint:** 5
**Priority:** P1 (high)
**Est. effort:** 2 hr
**Dependencies:** TASK-5.4

## Context

Users need a single, emotionally resonant number that answers "am I on track?" without reading charts or tables. A retirement readiness score (0–100) serves as the emotional anchor of the entire app — the thing you check monthly, the thing that motivates you to save more, the thing you screenshot and share.

Think of it like a credit score but for retirement preparedness. It synthesizes everything the projection engine knows into one number with a clear meaning.

## Requirements

### Backend: Score Computation

1. **Create scoring function in `backend/app/calculations/insights.py`** (or a new `readiness.py`):

   ```python
   @dataclass
   class ReadinessScore:
       score: int                    # 0–100
       label: str                    # "Fragile" | "En construction" | "Sur la bonne voie" | "Solide" | "Excellent"
       color: str                    # rose | amber | yellow | teal | emerald
       components: dict[str, int]    # Breakdown of sub-scores
       summary: str                  # One-sentence explanation
   
   def compute_readiness_score(
       projection: list[YearProjection],
       summary: ProjectionSummary,
       profile: ProjectionInput,
   ) -> ReadinessScore:
   ```

2. **Scoring components** (each 0–100, weighted average = final score):

   | Component | Weight | What it measures | 100 = | 0 = |
   |-----------|--------|------------------|-------|-----|
   | **Goal coverage** | 30% | Can retirement income meet the goal? | Income ≥ 120% of goal | Income < 30% of goal |
   | **Wealth durability** | 25% | How long does wealth last post-retirement? | Lasts to 95+ | Runs out within 5 years |
   | **Savings rate** | 15% | Current savings as % of net income | ≥ 25% | < 5% |
   | **Diversification** | 10% | Investment spread across vehicles | 4+ vehicles with meaningful allocation | 100% in one vehicle |
   | **Growth trajectory** | 10% | Is wealth growing faster than expenses? | Real growth > 3%/year | Wealth declining |
   | **Buffer adequacy** | 10% | Emergency fund (liquid savings) vs 6 months expenses | ≥ 6 months in liquid | < 1 month |

3. **Score bands:**
   - 0–20: "Fragile" (rose) — "Votre situation nécessite une action rapide"
   - 21–40: "En construction" (amber) — "Les fondations sont là, mais il y a du travail"
   - 41–60: "Sur la bonne voie" (yellow) — "Vous progressez, continuez sur cette lancée"
   - 61–80: "Solide" (teal) — "Votre plan tient la route"
   - 81–100: "Excellent" (emerald) — "Vous êtes en très bonne position"

4. **Component sub-score formulas:**

   ```python
   # Goal coverage: linear interpolation
   if retirement_income >= goal * 1.2:
       goal_score = 100
   elif retirement_income <= goal * 0.3:
       goal_score = 0
   else:
       goal_score = int((retirement_income / goal - 0.3) / 0.9 * 100)
   
   # Wealth durability
   if wealth_lasts_to >= 95:
       durability_score = 100
   elif wealth_lasts_to <= retirement_age + 5:
       durability_score = 0
   else:
       durability_score = int((wealth_lasts_to - retirement_age - 5) / 20 * 100)
   
   # Savings rate: % of net income saved monthly
   savings_pct = total_monthly_savings / net_monthly_income
   savings_score = min(100, int(savings_pct / 0.25 * 100))
   
   # Diversification: count vehicles with > 5% of total allocation
   meaningful_vehicles = sum(1 for v in allocations if v.monthly > total_monthly * 0.05)
   diversification_score = min(100, meaningful_vehicles * 25)
   
   # Growth trajectory: real wealth growth rate
   # Compare wealth at year 5 vs year 1, annualized
   
   # Buffer: liquid savings (Livret A + LDDS + AV euro) vs 6 months expenses
   liquid = livret_a.balance + ldds.balance + av_euro.balance
   months_buffer = liquid / monthly_expenses
   buffer_score = min(100, int(months_buffer / 6 * 100))
   ```

### API

5. **Add to projection response:**
   ```json
   {
     "readiness": {
       "score": 42,
       "label": "Sur la bonne voie",
       "color": "yellow",
       "components": {
         "goal_coverage": 35,
         "wealth_durability": 28,
         "savings_rate": 52,
         "diversification": 50,
         "growth_trajectory": 65,
         "buffer_adequacy": 40
       },
       "summary": "Votre plan progresse mais votre patrimoine ne couvre que 8 ans de retraite. Augmenter votre épargne de 300€/mois changerait la donne."
     }
   }
   ```

### Frontend

6. **Create `ReadinessGauge.svelte`** — prominent display at the top of the Runway page:
   - Large circular gauge (SVG arc) showing 0–100 with color gradient
   - Score number in the center (JetBrains Mono, large)
   - Label below ("Sur la bonne voie")
   - Summary text below the gauge
   - Expandable breakdown showing the 6 component scores as horizontal bars

7. **Placement:** Above the charts, below the scale selector. This is the first thing the user sees on the Runway page — the emotional hook.

8. **Animation:** Score animates from 0 to actual value on page load (smooth arc fill over 1.5s). When scale changes, animate the delta.

9. **If no goal is set:** Show score without the goal_coverage component (reweight others). Prompt: "Définissez un objectif pour affiner votre score."

## Acceptance Criteria

- [ ] Score computes correctly for all component weights
- [ ] Score bands map to correct labels and colors
- [ ] Gauge renders as an SVG arc with smooth animation
- [ ] Component breakdown expandable and clear
- [ ] Score updates when scale changes
- [ ] Summary text includes a specific recommendation
- [ ] Score is 0–20 for a user with zero savings and no goal
- [ ] Score is 80+ for a user with high savings, diversified allocation, and achievable goal
- [ ] Unit tests for scoring edge cases
- [ ] LEARNINGS.md updated

## Notes

- The score should feel honest, not gamified. Don't inflate scores to make users feel good. A score of 35 should mean "you genuinely need to do something different."
- The summary sentence is crucial — it should contain the single most impactful action. Reuse the top insight from TASK-5.4 if available.
- Consider adding historical score tracking in a future sprint (show score over time as the user makes changes).
