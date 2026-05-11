# TASK-7.11: Goal-Backward Solver

**Status:** TODO
**Sprint:** 7
**Priority:** P1 (high — the biggest advisory leap)
**Est. effort:** 3 hr
**Dependencies:** TASK-4.1

---

## Context

The user sets a goal (e.g. 4000€/mois passive at age 60) and the projection says "reached at 63" or "not reached." The obvious follow-up is: "what would it take to reach it at 58?" The system has all the inputs — it can solve backward. This task builds a goal-backward solver that finds the minimum changes needed to hit a target goal at a target age.

---

## Step-by-Step Instructions

### Step 1: Create the solver module

Create `backend/app/calculations/goal_solver.py`:

```python
"""Goal-backward solver — finds input changes to hit a target at a target age.

Strategy: binary search on each lever independently, then combine.
For each lever, find the minimum change that makes the goal achievable at
the target age. Then present the options ranked by feasibility.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.calculations.projection import ProjectionInput, project_timeline


@dataclass
class GoalSolution:
    """One way to reach the goal."""
    lever: str
    label: str
    description: str
    current_value: str
    required_value: str
    change_amount: str
    feasibility: str  # "easy", "moderate", "hard", "extreme"
    goal_year: int
    goal_age: int


def solve_goal(
    inp: ProjectionInput,
    target_monthly: Decimal,
    target_age: int,
    scale: str = "moderate",
) -> list[GoalSolution]:
    """Find what changes are needed to reach target_monthly by target_age.
    
    Tests each lever independently via binary search.
    Returns solutions ranked by feasibility (easiest first).
    """
    solutions: list[GoalSolution] = []
    
    birth_year = 2026 - (inp.target_age - (inp.target_age - inp.current_age))
    target_year = birth_year + target_age

    # Lever 1: Increase monthly savings
    savings_solution = _solve_savings(inp, target_monthly, target_year, target_age)
    if savings_solution:
        solutions.append(savings_solution)

    # Lever 2: Reduce monthly expenses
    expense_solution = _solve_expenses(inp, target_monthly, target_year, target_age)
    if expense_solution:
        solutions.append(expense_solution)

    # Lever 3: Increase CA growth rate
    growth_solution = _solve_growth(inp, target_monthly, target_year, target_age)
    if growth_solution:
        solutions.append(growth_solution)

    # Lever 4: Work longer (increase target age)
    age_solution = _solve_retirement_age(inp, target_monthly)
    if age_solution:
        solutions.append(age_solution)

    # Lever 5: Redirect savings to higher-yield vehicle (PEA)
    allocation_solution = _solve_allocation(inp, target_monthly, target_year, target_age)
    if allocation_solution:
        solutions.append(allocation_solution)

    # Rank by feasibility
    feasibility_order = {"easy": 0, "moderate": 1, "hard": 2, "extreme": 3}
    solutions.sort(key=lambda s: feasibility_order.get(s.feasibility, 99))

    return solutions


def _solve_savings(inp, target, target_year, target_age) -> GoalSolution | None:
    """Binary search: how much more monthly savings to hit the goal?"""
    current_savings = inp._total_monthly_savings()
    
    lo, hi = Decimal("0"), Decimal("5000")
    found = None
    
    for _ in range(20):  # 20 iterations of binary search
        mid = (lo + hi) / 2
        test_inp = copy.deepcopy(inp)
        _add_savings_to_input(test_inp, mid)
        timeline = project_timeline(test_inp)
        
        # Check if goal is reached at target_year
        target_entry = next((t for t in timeline if t.year == target_year), None)
        if target_entry and target_entry.total_monthly_income >= target:
            found = mid
            hi = mid
        else:
            lo = mid
    
    if found is None or found > Decimal("5000"):
        return None
    
    found = found.quantize(Decimal("10"))  # Round to nearest 10€
    
    feasibility = (
        "easy" if found <= 200 else
        "moderate" if found <= 500 else
        "hard" if found <= 1000 else
        "extreme"
    )
    
    return GoalSolution(
        lever="monthly_savings",
        label=f"Épargner {found}€/mois de plus",
        description=f"Passer de {current_savings}€ à {current_savings + found}€ d'épargne mensuelle",
        current_value=f"{current_savings}€/mois",
        required_value=f"{current_savings + found}€/mois",
        change_amount=f"+{found}€/mois",
        feasibility=feasibility,
        goal_year=target_year,
        goal_age=target_age,
    )


def _solve_expenses(inp, target, target_year, target_age) -> GoalSolution | None:
    """Binary search: how much less monthly expenses to hit the goal?"""
    current = inp.monthly_expenses_total
    
    lo, hi = Decimal("0"), min(current * Decimal("0.5"), Decimal("2000"))
    found = None
    
    for _ in range(20):
        mid = (lo + hi) / 2
        test_inp = copy.deepcopy(inp)
        test_inp.monthly_expenses_total = current - mid
        timeline = project_timeline(test_inp)
        
        target_entry = next((t for t in timeline if t.year == target_year), None)
        if target_entry and target_entry.total_monthly_income >= target:
            found = mid
            hi = mid
        else:
            lo = mid
    
    if found is None:
        return None
    
    found = found.quantize(Decimal("10"))
    feasibility = (
        "easy" if found <= 200 else
        "moderate" if found <= 500 else
        "hard" if found <= 1000 else
        "extreme"
    )
    
    return GoalSolution(
        lever="monthly_expenses",
        label=f"Réduire les dépenses de {found}€/mois",
        description=f"Passer de {current}€ à {current - found}€ de dépenses mensuelles",
        current_value=f"{current}€/mois",
        required_value=f"{current - found}€/mois",
        change_amount=f"-{found}€/mois",
        feasibility=feasibility,
        goal_year=target_year,
        goal_age=target_age,
    )


def _solve_growth(inp, target, target_year, target_age) -> GoalSolution | None:
    """Binary search: what growth rate is needed?"""
    current_rate = inp.growth_rate
    
    lo, hi = current_rate, Decimal("0.15")
    found = None
    
    for _ in range(20):
        mid = (lo + hi) / 2
        test_inp = copy.deepcopy(inp)
        test_inp.growth_rate = mid
        timeline = project_timeline(test_inp)
        
        target_entry = next((t for t in timeline if t.year == target_year), None)
        if target_entry and target_entry.total_monthly_income >= target:
            found = mid
            hi = mid
        else:
            lo = mid
    
    if found is None or found > Decimal("0.15"):
        return None
    
    delta = ((found - current_rate) * 100).quantize(Decimal("0.1"))
    feasibility = (
        "easy" if delta <= 1 else
        "moderate" if delta <= 3 else
        "hard" if delta <= 5 else
        "extreme"
    )
    
    return GoalSolution(
        lever="growth_rate",
        label=f"Augmenter la croissance CA de +{delta}%/an",
        description=f"Passer de {current_rate*100:.0f}% à {found*100:.1f}% de croissance annuelle",
        current_value=f"{current_rate*100:.0f}%/an",
        required_value=f"{found*100:.1f}%/an",
        change_amount=f"+{delta}%",
        feasibility=feasibility,
        goal_year=target_year,
        goal_age=target_age,
    )


def _solve_retirement_age(inp, target) -> GoalSolution | None:
    """Linear search: work how many more years?"""
    for extra_years in range(1, 11):
        test_inp = copy.deepcopy(inp)
        test_inp.target_age = inp.target_age + extra_years
        timeline = project_timeline(test_inp)
        
        if any(t.goal_reached for t in timeline):
            feasibility = (
                "easy" if extra_years <= 1 else
                "moderate" if extra_years <= 3 else
                "hard" if extra_years <= 5 else
                "extreme"
            )
            return GoalSolution(
                lever="retirement_age",
                label=f"Travailler {extra_years} an{'s' if extra_years > 1 else ''} de plus",
                description=f"Retraite à {inp.target_age + extra_years} ans au lieu de {inp.target_age}",
                current_value=f"Retraite à {inp.target_age}",
                required_value=f"Retraite à {inp.target_age + extra_years}",
                change_amount=f"+{extra_years} an{'s' if extra_years > 1 else ''}",
                feasibility=feasibility,
                goal_year=2026 + (inp.target_age + extra_years - inp.current_age),
                goal_age=inp.target_age + extra_years,
            )
    return None


def _solve_allocation(inp, target, target_year, target_age) -> GoalSolution | None:
    """Test: redirect 50% of savings to PEA."""
    test_inp = copy.deepcopy(inp)
    total = test_inp._total_monthly_savings()
    if total <= 0:
        return None
    
    # Redirect half to PEA
    redirect = total * Decimal("0.5")
    if "pea" in (test_inp.investment_allocations or {}):
        test_inp.investment_allocations["pea"]["monthly"] += redirect
    else:
        test_inp.investment_allocations = test_inp.investment_allocations or {}
        test_inp.investment_allocations["pea"] = {"monthly": redirect, "existing": Decimal("0")}
    
    # Reduce other allocations proportionally
    for k, v in (test_inp.investment_allocations or {}).items():
        if k != "pea" and v.get("monthly", Decimal("0")) > 0:
            v["monthly"] = v["monthly"] * Decimal("0.5")
    
    timeline = project_timeline(test_inp)
    target_entry = next((t for t in timeline if t.year == target_year), None)
    
    if target_entry and target_entry.total_monthly_income >= target:
        return GoalSolution(
            lever="allocation_pea",
            label="Rediriger 50% de l'épargne vers PEA",
            description=f"Allouer {redirect}€/mois au PEA au lieu des véhicules actuels",
            current_value="Allocation actuelle",
            required_value=f"PEA: {redirect}€/mois",
            change_amount=f"Rediriger {redirect}€/mois",
            feasibility="moderate",
            goal_year=target_year,
            goal_age=target_age,
        )
    return None


def _add_savings_to_input(inp: ProjectionInput, extra: Decimal):
    """Add extra monthly savings to the best available vehicle."""
    allocs = inp.investment_allocations or {}
    # Prefer PEA, then AV, then Livret A
    for vehicle in ["pea", "av_uc", "av_euro", "livret_a"]:
        if vehicle in allocs:
            allocs[vehicle]["monthly"] = allocs[vehicle].get("monthly", Decimal("0")) + extra
            return
    # No vehicle exists — add to Livret A
    allocs["livret_a"] = {"monthly": extra, "existing": Decimal("0")}
    inp.investment_allocations = allocs
```

### Step 2: API endpoint

File: `backend/app/routers/projection.py`

Add endpoint:

```python
@router.get("/goal-solver")
async def solve_goal_endpoint(
    target_monthly: float = Query(..., description="Target monthly income at retirement"),
    target_age: int = Query(..., description="Target age to reach the goal"),
    scale: str = Query(default="moderate"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inp = await _assemble_input(str(current_user.id), scale, db)
    inp.monthly_revenue_goal = Decimal(str(target_monthly))
    
    solutions = solve_goal(inp, Decimal(str(target_monthly)), target_age, scale)
    
    return {
        "target_monthly": target_monthly,
        "target_age": target_age,
        "solutions": [
            {
                "lever": s.lever,
                "label": s.label,
                "description": s.description,
                "current_value": s.current_value,
                "required_value": s.required_value,
                "change_amount": s.change_amount,
                "feasibility": s.feasibility,
            }
            for s in solutions
        ],
        "has_solution": len(solutions) > 0,
    }
```

### Step 3: Frontend — Goal solver card on Runway page

File: `frontend/src/routes/(app)/runway/+page.svelte`

Below the goal input section, add a "Comment y arriver ?" card:

```svelte
{#if goalTarget && goalAge}
  <button on:click={runGoalSolver}
    class="text-xs text-teal-400 hover:text-teal-300 mt-2">
    🎯 Comment atteindre {goalTarget}€/mois à {goalAge} ans ?
  </button>

  {#if goalSolutions}
    <div class="mt-3 space-y-2">
      <p class="text-xs font-semibold text-zinc-300">Pistes pour atteindre votre objectif :</p>
      {#each goalSolutions as sol}
        <div class="p-3 bg-zinc-900/40 border border-zinc-700/30 rounded-lg flex items-start gap-3">
          <span class="text-sm mt-0.5">
            {sol.feasibility === 'easy' ? '🟢' : sol.feasibility === 'moderate' ? '🟡' : sol.feasibility === 'hard' ? '🟠' : '🔴'}
          </span>
          <div>
            <p class="text-xs text-zinc-200 font-medium">{sol.label}</p>
            <p class="text-[10px] text-zinc-500">{sol.description}</p>
          </div>
          <span class="ml-auto text-xs font-mono text-teal-400 whitespace-nowrap">{sol.change_amount}</span>
        </div>
      {/each}
    </div>
  {/if}
{/if}
```

**Goal solver trigger:**
```typescript
let goalSolutions: any[] | null = null;

async function runGoalSolver() {
  const res = await api.get(`/projection/goal-solver?target_monthly=${goalTarget}&target_age=${goalAge}&scale=${currentScale}`);
  goalSolutions = res.solutions;
}
```

The solver needs the user to specify a target age. Add a small "À quel âge ?" input next to the goal input:

```svelte
<div class="flex gap-2 items-end">
  <Inp label="Objectif €/mois" bind:value={goalTarget} type="number" />
  <Inp label="À quel âge ?" bind:value={goalAge} type="number" min="50" max="80" className="w-24" />
  <button on:click={runGoalSolver} class="bg-teal-600 text-white text-xs rounded px-3 py-1.5">
    Calculer →
  </button>
</div>
```

### Step 4: Unit tests

Create `backend/tests/test_goal_solver.py`:
- Test with achievable goal (solution exists for at least 2 levers)
- Test with unachievable goal (solutions list is empty or all "extreme")
- Test that binary search converges (doesn't infinite loop)
- Test feasibility ranking (easy before hard)

---

## SCOPE BOUNDARY

- DO NOT combine multiple levers into a single compound solution. Each lever is tested independently.
- DO NOT add interactive "what if I do lever A AND lever B" — that's future work.
- DO NOT run more than 5 × 20 = 100 projection passes. If this is too slow (>2s), reduce binary search iterations to 15.
- DO NOT add the solver to the sensitivity analysis — they are separate features.
- The solver uses the same `project_timeline()` as the rest of the app. DO NOT create a simplified projection model.
- Expected: ~180 lines solver module, ~30 lines router, ~50 lines frontend.

## DONE WHEN

- [ ] `GET /api/projection/goal-solver?target_monthly=4000&target_age=58` returns solutions
- [ ] At least 4 levers tested (savings, expenses, growth, retirement age, allocation)
- [ ] Solutions ranked by feasibility (easy → extreme)
- [ ] Each solution shows current value, required value, and change amount
- [ ] Frontend card renders below goal input on Runway page
- [ ] "À quel âge ?" input added next to goal input
- [ ] Performance: response in < 3 seconds
- [ ] Tests pass
