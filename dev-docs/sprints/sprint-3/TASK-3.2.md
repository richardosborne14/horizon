# TASK-3.2: Project Model & P&L Computation

**Status:** BACKLOG
**Sprint:** 3
**Priority:** P0 (critical)
**Est. effort:** 2 hr
**Dependencies:** TASK-1.1

## Context

Projects are the "active wealth building" lever. Two types:

1. **Investment projects** (gîte, rental apartment, business venture) — have a purchase cost, generate annual income and annual expenses, get taxed, and produce a net yield. The user builds a mini P&L per project and sees the real return after costs and tax.

2. **Life events** (wedding, big renovation, world trip, moving) — one-time costs at a specific year. No income, just an expense spike that the projection engine accounts for.

The P&L computation for investment projects runs server-side — the frontend displays it but doesn't calculate it.

## Requirements

1. Create `backend/app/models/project.py`:

```python
class Project(Base):
    __tablename__ = "projects"

    id           = Column(UUID, primary_key=True, default=uuid4)
    user_id      = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    project_type = Column(String(20), nullable=False)  # "invest" or "event"
    label        = Column(String(200), nullable=False)

    # Investment fields (null for events)
    start_year       = Column(Integer, nullable=True)
    purchase_cost    = Column(Numeric(12, 2), nullable=True)
    annual_income    = Column(Numeric(10, 2), nullable=True)
    annual_expenses  = Column(Numeric(10, 2), nullable=True)
    tax_rate         = Column(Numeric(5, 3), nullable=True)  # e.g. 0.300

    # Event fields (null for investments)
    event_year = Column(Integer, nullable=True)
    event_cost = Column(Numeric(12, 2), nullable=True)

    # Common
    notes     = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

2. Pydantic schemas in `backend/app/schemas/project.py`:

```python
class ProjectInvestmentCreate(BaseModel):
    label: str = Field(max_length=200)
    start_year: int = Field(ge=2024, le=2080)
    purchase_cost: Decimal = Field(ge=0)
    annual_income: Decimal = Field(ge=0)
    annual_expenses: Decimal = Field(ge=0)
    tax_rate: Decimal = Field(ge=0, le=1)
    notes: str | None = None

class ProjectEventCreate(BaseModel):
    label: str = Field(max_length=200)
    event_year: int = Field(ge=2024, le=2080)
    event_cost: Decimal = Field(ge=0)
    notes: str | None = None

class ProjectPNL(BaseModel):
    """Computed P&L for investment projects."""
    gross_annual: Decimal        # income - expenses
    tax_amount: Decimal          # gross * tax_rate
    net_annual: Decimal          # gross - tax
    yield_pct: Decimal | None    # net / purchase_cost (null if cost=0)
    monthly_net: Decimal         # net / 12

class ProjectRead(BaseModel):
    id: UUID
    project_type: str
    label: str
    # Investment fields
    start_year: int | None
    purchase_cost: Decimal | None
    annual_income: Decimal | None
    annual_expenses: Decimal | None
    tax_rate: Decimal | None
    # Event fields
    event_year: int | None
    event_cost: Decimal | None
    # Computed
    pnl: ProjectPNL | None  # Only for invest type
    notes: str | None
    is_active: bool
```

3. Create `backend/app/calculations/project_pnl.py`:

```python
def compute_pnl(
    annual_income: Decimal,
    annual_expenses: Decimal,
    tax_rate: Decimal,
    purchase_cost: Decimal,
) -> ProjectPNL:
    gross = annual_income - annual_expenses
    tax = max(Decimal("0"), gross * tax_rate)
    net = gross - tax
    yield_pct = (net / purchase_cost) if purchase_cost > 0 else None
    return ProjectPNL(
        gross_annual=gross,
        tax_amount=tax,
        net_annual=net,
        yield_pct=yield_pct,
        monthly_net=net / 12,
    )
```

4. CRUD router `backend/app/routers/projects.py`:
   - `GET /api/projects` — list all for user (active only by default)
   - `GET /api/projects?type=invest` — filter by type
   - `POST /api/projects/investment` — create investment project
   - `POST /api/projects/event` — create life event
   - `PUT /api/projects/{id}` — update
   - `DELETE /api/projects/{id}` — soft delete
   - All investment project reads include computed P&L

5. Alembic migration

6. Unit tests:
   - P&L computation: 80k purchase, 8k income, 2.5k expenses, 30% tax → gross 5 500, tax 1 650, net 3 850, yield 4.81%
   - Edge case: 0 income → negative gross → tax = 0 (no negative tax)
   - Edge case: 0 purchase cost → yield = null
   - CRUD for both types

## Technical Approach

### Files to Create
- `backend/app/models/project.py`
- `backend/app/schemas/project.py`
- `backend/app/calculations/project_pnl.py`
- `backend/app/routers/projects.py`
- `backend/alembic/versions/xxxx_add_projects.py`
- `backend/tests/test_projects.py`

### Design Decision: One Table, Two Create Schemas
Single `projects` table with nullable fields per type (investment fields null for events, event fields null for investments). Separate create schemas enforce the right fields per type. The router has separate POST endpoints per type for clean validation.

## Acceptance Criteria

- [ ] POST investment: creates with all fields, returns with computed P&L
- [ ] POST event: creates with year + cost
- [ ] P&L math: 80k/8k/2.5k/30% → net 3 850€/yr, yield 4.81%
- [ ] P&L with 0 income: gross negative, tax = 0, net negative
- [ ] P&L with 0 purchase cost: yield = null
- [ ] GET returns investments with P&L, events without
- [ ] Filter by type works
- [ ] Soft delete works
- [ ] User scoping (A can't see B's projects)
- [ ] Unit tests pass
- [ ] LEARNINGS.md updated

## Notes

- The P&L is a snapshot computation, not stored. It's recomputed on every read. This means changing income/expenses immediately reflects in the P&L without a separate "recalculate" step.
- The projection engine (Sprint 4) uses a more nuanced version: income grows at ~2%/year (rental market), expenses inflate, and the whole thing feeds into the year-by-year timeline. The simple P&L here is for the "at a glance" display on the Projects page.
- `tax_rate` for rental income depends on the regime (micro-BIC at 50% abattement, or réel). For MVP the user enters their effective rate. A future calculator could help determine the optimal regime.
- The `notes` field is for the user to jot reminders ("Travaux toit prévus en 2030", "Bail renouvelé en 2032").
