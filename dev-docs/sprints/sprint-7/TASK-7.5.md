# TASK-7.5: Income Source Model & API

**Status:** TODO
**Sprint:** 7
**Priority:** P1 (high — replaces single CA field with rich income model)
**Est. effort:** 3 hr
**Dependencies:** None

---

## Context

The current revenue model is one field: `monthly_gross_ca` on UserProfile. This task replaces it with tracked income sources — each with a label, amount, duration, growth rate, and confidence level. Sources can belong to the user or spouse. The old `monthly_gross_ca` field stays for backward compatibility (computed from active sources).

---

## Step-by-Step Instructions

### Step 1: Create IncomeSource model

Create `backend/app/models/income_source.py`:

```python
"""Income source model — individual revenue streams for user or spouse."""
from uuid import uuid4
from sqlalchemy import (
    Column, String, Date, Boolean, Integer, Numeric, Text,
    ForeignKey, DateTime, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class IncomeSource(Base):
    __tablename__ = "income_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Who earns this
    earner = Column(String(10), nullable=False, server_default="user")
    # "user" or "spouse"

    # Source identity
    label = Column(String(200), nullable=False)
    source_type = Column(String(30), nullable=False, server_default="client")
    # client, product, salary, dividends, rental, pension, sale, other

    # Revenue
    amount = Column(Numeric(12, 2), nullable=False)
    frequency = Column(String(20), nullable=False, server_default="monthly")
    # monthly, annual, one_time

    # Duration
    start_date = Column(Date, nullable=True)   # null = already active
    end_date = Column(Date, nullable=True)     # null = ongoing
    confidence = Column(String(20), nullable=False, server_default="high")
    # high (signed contract), medium (verbal), low (speculative)

    # Growth
    annual_growth_rate = Column(Numeric(5, 4), nullable=True)

    # Tax treatment
    is_ae_revenue = Column(Boolean, nullable=False, server_default="true")
    # If true → subject to AE cotisations. If false (dividends, salary) → different treatment.

    # Status
    is_active = Column(Boolean, nullable=False, server_default="true")
    sort_order = Column(Integer, nullable=False, server_default="0")
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="income_sources")
```

### Step 2: Alembic migration

```bash
cd backend && alembic revision --autogenerate -m "add income_sources table"
alembic upgrade head
```

### Step 3: Pydantic schemas

Create `backend/app/schemas/income_source.py`:

- `IncomeSourceCreate`: all fields, `label` and `amount` required
- `IncomeSourceUpdate`: all fields optional
- `IncomeSourceRead`: all fields + `id`, `user_id`, timestamps

Follow the same pattern as `backend/app/schemas/career.py`.

### Step 4: CRUD Router

Create `backend/app/routers/income_sources.py`:

Endpoints:
- `GET /api/income-sources` → list all for user. Optional query param `?earner=user|spouse`
- `POST /api/income-sources` → create
- `PUT /api/income-sources/{id}` → update (partial)
- `DELETE /api/income-sources/{id}` → delete

Plus a summary endpoint:

- `GET /api/income-sources/summary` → returns:

```json
{
  "user": {
    "current_monthly_total": "5500.00",
    "sources_count": 3,
    "guaranteed_monthly": "4500.00",
    "speculative_monthly": "1000.00",
    "ending_within_12_months": [
      {"label": "Client Alpha", "ends": "2027-06-30", "monthly": "2000.00"}
    ]
  },
  "spouse": {
    "current_monthly_total": "2800.00",
    "sources_count": 1,
    "guaranteed_monthly": "2800.00",
    "speculative_monthly": "0.00",
    "ending_within_12_months": []
  },
  "household_monthly_total": "8300.00"
}
```

**Summary calculation rules:**
- "current" = `start_date` is null or ≤ today, AND `end_date` is null or > today, AND `is_active = true`
- "guaranteed" = current AND `confidence = "high"`
- "speculative" = current AND `confidence != "high"`
- "ending within 12 months" = current AND `end_date` is within next 365 days
- For `frequency = "annual"`: divide by 12 for monthly total
- For `frequency = "one_time"`: exclude from monthly totals (these appear in future events only)

### Step 5: Migration helper — auto-create from existing CA

In the router's `GET /api/income-sources` endpoint, if the user has zero income sources but `monthly_gross_ca > 0` on their profile, auto-create one:

```python
if not sources and profile.monthly_gross_ca and profile.monthly_gross_ca > 0:
    auto_source = IncomeSource(
        user_id=user_id,
        earner="user",
        label="Activité principale",
        source_type="client",
        amount=profile.monthly_gross_ca,
        frequency="monthly",
        confidence="high",
        is_ae_revenue=True,
    )
    db.add(auto_source)
    await db.commit()
    sources = [auto_source]
```

### Step 6: Backward compatibility — keep monthly_gross_ca in sync

When income sources change, update `profile.monthly_gross_ca` to match the sum of active user-earner monthly AE sources. Add a helper:

```python
async def sync_profile_ca(user_id: str, db: AsyncSession):
    """Recompute monthly_gross_ca from active income sources."""
    result = await db.execute(
        select(func.sum(IncomeSource.amount))
        .where(IncomeSource.user_id == user_id)
        .where(IncomeSource.earner == "user")
        .where(IncomeSource.is_ae_revenue == True)
        .where(IncomeSource.is_active == True)
        .where(IncomeSource.frequency == "monthly")
        .where(or_(IncomeSource.start_date == None, IncomeSource.start_date <= func.current_date()))
        .where(or_(IncomeSource.end_date == None, IncomeSource.end_date > func.current_date()))
    )
    total = result.scalar() or Decimal("0")
    # Add annual sources / 12
    annual_result = await db.execute(
        select(func.sum(IncomeSource.amount))
        .where(IncomeSource.user_id == user_id)
        .where(IncomeSource.earner == "user")
        .where(IncomeSource.is_ae_revenue == True)
        .where(IncomeSource.is_active == True)
        .where(IncomeSource.frequency == "annual")
        .where(or_(IncomeSource.start_date == None, IncomeSource.start_date <= func.current_date()))
        .where(or_(IncomeSource.end_date == None, IncomeSource.end_date > func.current_date()))
    )
    annual = annual_result.scalar() or Decimal("0")
    total += annual / 12
    
    profile = await get_profile(user_id, db)
    profile.monthly_gross_ca = total
    await db.commit()
```

Call `sync_profile_ca()` after every create/update/delete of an income source.

### Step 7: Register router

File: `backend/app/routers/__init__.py` — add income_sources router.

### Step 8: Unit tests

Create `backend/tests/test_income_sources.py`:
- Test CRUD (create, list, update, delete)
- Test earner filter (`?earner=spouse`)
- Test summary aggregation (monthly, annual, one_time handling)
- Test auto-creation from existing CA
- Test `sync_profile_ca` updates profile correctly
- Test confidence filtering in summary

---

## SCOPE BOUNDARY

- DO NOT build the frontend. That's TASK-7.6.
- DO NOT modify the projection engine. That's TASK-7.8.
- DO NOT add income source presets/templates. That's a frontend concern (TASK-7.6).
- DO NOT compute projected income timelines. The projection engine does that.
- One-time sources are stored but excluded from monthly totals in the summary. They appear only in future_events.

## DONE WHEN

- [ ] Migration creates `income_sources` table
- [ ] CRUD endpoints work with auth, user-scoped
- [ ] `?earner=spouse` filter works
- [ ] Summary endpoint returns correct totals for user and spouse
- [ ] Auto-migration creates source from existing `monthly_gross_ca`
- [ ] `sync_profile_ca` keeps profile field in sync after source changes
- [ ] One-time sources excluded from monthly totals
- [ ] Annual sources divided by 12 in monthly totals
- [ ] All tests pass
