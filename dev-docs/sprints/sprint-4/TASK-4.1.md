# TASK-4.1: Projection Engine — Core Calculation

**Status:** BACKLOG
**Sprint:** 4
**Priority:** P0 (critical)
**Est. effort:** Half day
**Dependencies:** TASK-1.2, TASK-1.3, TASK-1.4, TASK-2.1, TASK-2.3, TASK-2.4, TASK-3.1, TASK-3.2

## Context

The heart of Horizon 30. A pure calculation function that reads all user data and produces a `list[YearProjection]` — one entry per year from current age to target retirement age. Every financial dimension is computed per year: income, charges, expenses (base + life entities + recurring), project income/expenses, CAF, tax credits, investment compounding, and passive income potential.

This is the most complex function in the codebase. It must be:
- **Correct** — compounding math, lifecycle timing, rate lookups all verified
- **Deterministic** — same inputs always produce same outputs
- **Fast** — < 500ms for a 30-year projection with 10+ life entities
- **Testable** — pure function, no side effects, all data passed in

## Requirements

1. Create `backend/app/calculations/projection.py`

2. **Input data structure** — the engine receives a flat data object, NOT raw DB queries. The API layer (TASK-4.2) assembles this from the DB.

```python
@dataclass
class ProjectionInput:
    # Identity
    current_age: int
    target_age: int
    
    # Revenue
    monthly_gross: Decimal
    growth_rate: Decimal
    ae_activity_type: str
    
    # Expenses
    monthly_expenses_total: Decimal  # sum of all expense categories
    
    # Scale
    scale: str  # "optimistic" | "moderate" | "pessimistic"
    
    # Life entities — pre-processed into a flat cost schedule
    # list of: {"entity_type", "entity_name", "entity_age_at_start", "cost_events": [...]}
    life_entities: list[dict]
    
    # Recurring expenses
    # list of: {"label", "annual_amount", "from_year", "to_year"}
    recurring_expenses: list[dict]
    
    # Investments
    # dict of vehicle_key → {"balance": Decimal, "monthly": Decimal}
    allocations: dict[str, dict]
    
    # Projects
    # list of: {"type": "invest"|"event", ...project fields}
    projects: list[dict]
    
    # CAF
    kids_birth_dates: list[date]  # for CAF estimation per year
    caf_override: Decimal | None  # null = auto-estimate
    household_income_for_caf: Decimal  # for CAF income test
    
    # Tax breaks
    cesu_annual: Decimal
    charity_annual: Decimal
    
    # Status change
    status_change_enabled: bool
    status_change_year: int | None
    status_change_savings: Decimal | None
    
    # Goal
    monthly_revenue_goal: Decimal | None
```

3. **Output structure:**

```python
class YearProjection(BaseModel):
    year: int
    age: int
    
    # Revenue
    gross_annual: Decimal
    ae_rate: Decimal
    charges: Decimal          # gross × ae_rate
    cfe: Decimal
    
    # Expenses
    base_expenses: Decimal     # monthly × 12, inflation-adjusted
    kid_expenses: Decimal
    pet_expenses: Decimal
    car_expenses: Decimal
    tech_expenses: Decimal
    recurring_expenses: Decimal
    project_expenses: Decimal  # investment running costs + event one-time costs
    project_income: Decimal    # investment rental income
    
    # Income additions
    caf_annual: Decimal
    tax_credits: Decimal       # CESU + charity
    status_bonus: Decimal
    
    # Net
    total_income: Decimal      # gross + project_income + caf + tax_credits
    total_outgoing: Decimal    # charges + cfe + all expense categories
    net_annual: Decimal        # total_income - total_outgoing + status_bonus
    
    # Investments
    year_invested: Decimal
    year_returns: Decimal
    total_wealth: Decimal      # sum of all vehicle balances
    
    # Derived
    passive_monthly: Decimal          # total_wealth × 4% / 12
    total_monthly_income: Decimal     # (gross + project_income + caf) / 12 + passive_monthly
    goal_reached: bool
```

4. **Year-by-year computation loop:**

```python
def project_timeline(inp: ProjectionInput) -> list[YearProjection]:
    years = inp.target_age - inp.current_age
    scale = INFLATION_SCALES[inp.scale]
    balances = {k: v["balance"] for k, v in inp.allocations.items()}
    timeline = []
    
    for y in range(years):
        year = THIS_YEAR + y
        age = inp.current_age + y
        infl = (1 + scale["inflation"]) ** y
        cost_factor = (1 + scale["cost_living"]) ** y
        
        # ── Revenue ──────────────────────────────────
        gross = inp.monthly_gross * 12 * (1 + inp.growth_rate) ** y
        ae_rate = get_ae_rate(inp.ae_activity_type, year)
        charges = gross * ae_rate
        cfe = Decimal("300") * infl
        
        # ── Status change ────────────────────────────
        status_bonus = Decimal("0")
        if inp.status_change_enabled and year >= (inp.status_change_year or 9999):
            status_bonus = inp.status_change_savings or Decimal("0")
        
        # ── Base expenses ────────────────────────────
        base_exp = inp.monthly_expenses_total * 12 * cost_factor
        
        # ── Life entity expenses ─────────────────────
        kid_exp = pet_exp = car_exp = tech_exp = Decimal("0")
        for entity in inp.life_entities:
            entity_age = entity["entity_age_at_start"] + y
            for evt in entity["cost_events"]:
                if not evt.get("is_active", True):
                    continue
                if entity_age < evt["from_age"] or entity_age > evt["to_age"]:
                    continue
                amount = Decimal(str(evt["amount"])) * infl
                if evt["frequency"] == "monthly":
                    amount *= 12
                elif evt["frequency"] == "once":
                    # Only fire in the exact year the entity hits from_age
                    if entity_age != evt["from_age"]:
                        continue
                # Route to the right bucket
                if entity["entity_type"] == "kid": kid_exp += amount
                elif entity["entity_type"] == "pet": pet_exp += amount
                elif entity["entity_type"] == "car": car_exp += amount
                elif entity["entity_type"] == "tech": tech_exp += amount
        
        # ── Recurring expenses ───────────────────────
        rec_exp = Decimal("0")
        for r in inp.recurring_expenses:
            if year >= r["from_year"] and year <= r["to_year"]:
                rec_exp += Decimal(str(r["annual_amount"])) * infl
        
        # ── Projects ─────────────────────────────────
        proj_exp = proj_inc = Decimal("0")
        for p in inp.projects:
            if p["type"] == "invest" and year >= p.get("start_year", 9999):
                if year == p["start_year"]:
                    proj_exp += Decimal(str(p.get("purchase_cost", 0)))
                owned = year - p["start_year"]
                if owned > 0:
                    inc = Decimal(str(p.get("annual_income", 0))) * (Decimal("1.02") ** owned)
                    exp = Decimal(str(p.get("annual_expenses", 0))) * infl
                    tax = max(Decimal("0"), (inc - exp)) * Decimal(str(p.get("tax_rate", "0.30")))
                    proj_inc += inc
                    proj_exp += exp + tax
            elif p["type"] == "event" and year == p.get("event_year"):
                proj_exp += Decimal(str(p.get("event_cost", 0)))
        
        # ── CAF ──────────────────────────────────────
        kids_under_20 = sum(1 for bd in inp.kids_birth_dates
                           if (date(year, 1, 1) - bd).days // 365 < 20)
        if inp.caf_override is not None and kids_under_20 > 0:
            caf = inp.caf_override * 12 * Decimal("1.015") ** y
        else:
            caf = estimate_monthly_caf(kids_under_20, gross / 12, year) * 12
        
        # ── Tax credits ──────────────────────────────
        cesu_credit = min(inp.cesu_annual * infl * Decimal("0.5"), Decimal("6000"))
        charity_credit = min(inp.charity_annual * infl * Decimal("0.66"), Decimal("20000"))
        tax_credits = cesu_credit + charity_credit
        
        # ── Net ──────────────────────────────────────
        total_income = gross + proj_inc + caf + tax_credits
        total_outgoing = charges + cfe + base_exp + kid_exp + pet_exp + car_exp + tech_exp + rec_exp + proj_exp
        net = total_income - total_outgoing + status_bonus
        
        # ── Investments ──────────────────────────────
        year_invested = year_returns = Decimal("0")
        for vk, alloc in inp.allocations.items():
            monthly = Decimal(str(alloc.get("monthly", 0)))
            if monthly <= 0:
                continue
            spec = VEHICLE_SPECS.get(vk)
            if not spec:
                continue
            bal = balances.get(vk, Decimal("0"))
            contrib = monthly * 12
            eff_rate = max(Decimal("0.005"), spec["rate"] - scale["inflation"] * Decimal("0.25"))
            returns = bal * eff_rate
            net_ret = returns if spec["tax_free"] else returns * (1 - spec.get("tax_rate", Decimal("0")))
            ceiling = spec.get("ceiling")
            new_bal = bal + contrib + net_ret
            if ceiling:
                new_bal = min(new_bal, ceiling * infl)
            balances[vk] = new_bal
            year_invested += contrib
            year_returns += net_ret
        
        wealth = sum(balances.values())
        passive = wealth * Decimal("0.04") / 12
        total_monthly = (gross + proj_inc + caf) / 12 + passive
        
        timeline.append(YearProjection(
            year=year, age=age, gross_annual=gross, ae_rate=ae_rate,
            charges=charges, cfe=cfe, base_expenses=base_exp,
            kid_expenses=kid_exp, pet_expenses=pet_exp,
            car_expenses=car_exp, tech_expenses=tech_exp,
            recurring_expenses=rec_exp, project_expenses=proj_exp,
            project_income=proj_inc, caf_annual=caf, tax_credits=tax_credits,
            status_bonus=status_bonus, total_income=total_income,
            total_outgoing=total_outgoing, net_annual=net,
            year_invested=year_invested, year_returns=year_returns,
            total_wealth=wealth, passive_monthly=passive,
            total_monthly_income=total_monthly,
            goal_reached=bool(inp.monthly_revenue_goal and total_monthly >= inp.monthly_revenue_goal),
        ))
    
    return timeline
```

5. **Helper: compute milestones**

```python
def compute_milestones(timeline: list[YearProjection]) -> list[dict]:
    targets = [(100_000, "100k€"), (250_000, "250k€"), (500_000, "500k€"), (1_000_000, "1M€")]
    milestones = []
    for amount, label in targets:
        hit = next((t for t in timeline if t.total_wealth >= amount), None)
        if hit:
            milestones.append({"label": label, "year": hit.year, "age": hit.age})
    return milestones
```

6. **Helper: find goal year**

```python
def find_goal_year(timeline: list[YearProjection]) -> dict | None:
    hit = next((t for t in timeline if t.goal_reached), None)
    return {"year": hit.year, "age": hit.age} if hit else None
```

7. **Unit tests** (`backend/tests/test_projection.py`) — 3 scenarios minimum:

   **Scenario A — Bare minimum:**
   Age 40→70, CA 3000€/month, BNC, no investments, no projects, no kids. Verify: charges increase over time as AE rates rise, base expenses inflate, net_annual decreases in real terms, total_wealth = 0.

   **Scenario B — Moderate saver:**
   Age 40→70, CA 5000€/month, 3% growth, 2 kids (ages 10 and 1), 1 dog, 1 car, 950€/month in savings across 4 vehicles, 1 gîte project in 2035. Verify: kid expenses taper off, car replacement fires at correct year, gîte income appears from 2036, wealth crosses 100k at expected year.

   **Scenario C — Aggressive investor:**
   Age 40→70, CA 8000€/month, 6% growth, EIRL switch in 2028 (+5000€/year), 1500€/month in PEA/SCPI/AV-UC, 2 investment projects. Verify: status bonus from 2028, high wealth accumulation, passive income covers expenses before target age.

   Each test hand-calculates at least year 0, year 5, and year 29 and asserts to within 1€ rounding tolerance.

## Technical Approach

### Files to Create
- `backend/app/calculations/projection.py`
- `backend/tests/test_projection.py`

### Key Design Decisions

**Pure function, no DB access.** The engine receives a `ProjectionInput` dataclass and returns `list[YearProjection]`. The API layer (TASK-4.2) is responsible for assembling the input from the database. This makes the engine testable without any DB setup.

**All Decimal, no float.** Every financial value is Decimal throughout. The Pydantic models serialize to string in JSON. The frontend parses and formats.

**Effective rate adjustment.** Investment returns are reduced by `inflation × 0.25` to model real (inflation-adjusted) returns conservatively. A 7% PEA in a 2.5% inflation environment yields an effective ~6.375%. This is a simplification of real return modeling but directionally correct.

**Once-frequency events.** Events with `frequency: "once"` fire only in the year the entity reaches `from_age`. This is critical for car replacements and kid milestones (permis, first car). The check is `entity_age == from_age`, not `entity_age >= from_age`.

**Investment ceiling inflation.** Vehicle ceilings (Livret A 22 950€) are adjusted for inflation because regulators periodically raise them. This prevents the engine from capping contributions unrealistically far in the future.

## Acceptance Criteria

- [ ] Engine computes 30-year timeline without error for all 3 test scenarios
- [ ] AE rates change over time (not flat) — verify rate at year 0 vs year 10
- [ ] Kid expenses: crèche active for kid age 0-3, stops at 4 (September rule)
- [ ] Kid expenses: études appear at age 18-23, then stop
- [ ] Car CT events fire at ages 4, 6, 8 only (once frequency)
- [ ] Car replacement fires once at cycle age
- [ ] Investment balances compound correctly year over year
- [ ] Livret A balance doesn't exceed ceiling (inflation-adjusted)
- [ ] Project income grows at 2%/year, expenses inflate
- [ ] Project purchase cost fires only in start_year
- [ ] Life event cost fires only in event_year
- [ ] CAF decreases when kids age past 20
- [ ] Status bonus applies from change_year onward
- [ ] Goal detection correct: first year where total_monthly >= goal
- [ ] Milestones detected at correct wealth thresholds
- [ ] Scenario B hand-calc matches engine output at years 0, 5, 29
- [ ] Performance: 30-year projection with 10 entities completes in < 200ms
- [ ] All 3 test scenarios pass
- [ ] LEARNINGS.md updated

## Notes

- This is the highest-risk task in the project. Allocate extra time for debugging compounding edge cases.
- The "once" frequency logic is subtle. A cost event `{from_age: 18, to_age: 18, frequency: "once"}` fires exactly once when the entity turns 18. If from_age != to_age for a "once" event, that's a data error — the engine should fire at from_age only.
- The 4% rule for passive income is a simplification of the Trinity Study withdrawal rate. It assumes a diversified portfolio and 30-year horizon. Not all vehicles support 4% withdrawal (PER is locked, Livret A has a ceiling). For MVP, apply 4% to total wealth uniformly. A future enhancement could apply different rates per vehicle.
- Investment returns are computed on beginning-of-year balance, then contributions are added. This is slightly conservative (real contributions compound intra-year). Acceptable simplification.
