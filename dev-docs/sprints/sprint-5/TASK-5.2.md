# TASK-5.2: Post-Retirement Phase Modeling

**Status:** TODO
**Sprint:** 5
**Priority:** P0 (critical — the biggest value gap in the tool)
**Est. effort:** 3 hr
**Dependencies:** TASK-4.1

## Context

The projection engine currently stops at the target retirement age (default 70). It shows "Patrimoine à 70 ans: 163.9k€" and "Revenu passif mensuel: 546€" — and then... nothing. The user has no idea how long their money will last, whether it covers their expenses, or when they'll run out.

This is the single biggest gap in Horizon's value proposition. The tool promises to help freelancers plan for retirement, but it only models the accumulation phase. The decumulation phase — the part where the user actually *lives* off their savings — is where the real anxiety lives and where the real value is.

## Requirements

### Backend: Extend the Projection Engine

1. **Add post-retirement timeline** to `backend/app/calculations/projection.py`:
   - After the last accumulation year (target retirement age), continue the simulation for 25 more years (to age 95, configurable)
   - In post-retirement years:
     - **Work income drops to zero** (no more CA)
     - **Expenses continue**, inflation-adjusted (the user still pays rent, eats food, drives a car)
     - **Kid expenses phase out** naturally (the lifecycle engine already handles this)
     - **Investment balances draw down**: withdraw enough to cover the gap between passive income (pension + investment returns + project income) and expenses
     - **Pension income begins** (see TASK-5.3 — for now use a placeholder of 0€, or a user-configurable override field)
     - **Project rental income continues** (if the user has investment projects)
     - **Wealth decreases** as savings are consumed
   - Track the year when **wealth hits zero** ("épuisement du patrimoine")
   - Track the year when **total income falls below expenses** ("déficit")

2. **New fields in `YearProjection`** for post-retirement years:
   ```python
   is_retirement: bool = False       # True for years after retirement age
   pension_monthly: Decimal = 0      # State pension (placeholder until 5.3)
   withdrawal_annual: Decimal = 0    # Amount withdrawn from savings
   years_of_runway: int | None = None  # How many years of savings remain at current burn rate
   ```

3. **New summary fields** in the projection response:
   ```python
   wealth_exhaustion_age: int | None    # Age when patrimoine hits 0 (None = never in simulation)
   retirement_monthly_income: Decimal   # Total monthly income at retirement start (pension + passive + projects)
   retirement_monthly_gap: Decimal      # Gap between retirement income and expenses (negative = shortfall)
   retirement_runway_years: int | None  # Years wealth lasts post-retirement
   ```

4. **Withdrawal strategy**: Use the "bucket" approach for MVP:
   - First, spend returns/dividends from investments
   - Then, draw from liquid accounts first (Livret A → LDDS → AV)
   - PER unlocks at retirement (add this to available balance)
   - PEA stays invested if possible (tax efficiency)
   - Track remaining balance per vehicle per year

### Frontend: Extend the Runway Page

5. **Extend charts** to show the full lifecycle:
   - Wealth trajectory chart continues past retirement — shows the drawdown curve
   - Add a visual marker at the retirement age (vertical dashed line labeled "Retraite")
   - If wealth hits zero, mark that point prominently (red dot + label "Épuisement")
   - Income chart shows the transition: work income drops, pension kicks in

6. **Extend the projection table** to include post-retirement rows:
   - Show every 5 years post-retirement (75, 80, 85, 90, 95)
   - New columns or adapted columns: "Retraits" instead of "CA Brut", "Pension" column
   - Color the row background subtly differently for retirement years (e.g., slightly warmer zinc)

7. **New hero stats for post-retirement**:
   - "Votre patrimoine dure jusqu'à X ans" (or "au-delà de 95 ans" if it never runs out)
   - "Revenu mensuel à la retraite: X€" (pension + passive + projects)
   - "Écart mensuel: +X€" or "-X€" (vs current expenses, inflation-adjusted)

8. **Add `post_retirement_years` to UserProfile** (default 25, meaning simulate to age 95). Allow user to adjust if they want to plan to 100.

### Calculation Logic

The core loop for post-retirement years:

```
For each year after retirement:
  expenses = base_expenses * inflation^years + kid_costs + pet_costs + car_costs + tech_costs
  income = pension + project_rental_income + investment_returns
  gap = expenses - income
  
  if gap > 0:
    # Need to withdraw from savings
    withdraw(gap, from liquid accounts first)
  else:
    # Surplus — reinvest or let it compound
    
  if total_wealth <= 0:
    mark wealth_exhaustion_age = current_age
    break
```

## Acceptance Criteria

- [ ] Projection extends 25 years past retirement age
- [ ] Work income correctly drops to zero at retirement
- [ ] Expenses continue with inflation adjustment
- [ ] Wealth drawdown computed correctly (withdrawals from savings)
- [ ] Wealth exhaustion age computed and displayed
- [ ] Charts show full lifecycle with retirement marker
- [ ] Table includes post-retirement rows
- [ ] Hero stats updated with retirement readiness metrics
- [ ] Hand-verified: user with 163.9k€ at 70, 546€ passive, 3,705€ expenses → wealth exhaustion in ~4 years (confirming the urgency of saving more)
- [ ] Unit tests for post-retirement scenarios: surplus (never runs out), deficit (runs out at age X), breakeven
- [ ] LEARNINGS.md updated

## Notes

- This task will likely reveal that many users' projections are much more alarming than the current tool suggests. A user with 163.9k€ and 3,705€/month expenses will burn through savings in roughly 4 years post-retirement if pension is zero. That's the honest truth the tool should show — it's why this feature is critical.
- The PER vehicle unlocking at retirement is an important detail — it's currently "blocked" but becomes available at retirement age, which boosts the available balance.
- Consider adding a "safety margin" display: "Pour tenir jusqu'à 95 ans, épargnez X€/mois de plus" — but this might belong in TASK-5.4 (Insights).
