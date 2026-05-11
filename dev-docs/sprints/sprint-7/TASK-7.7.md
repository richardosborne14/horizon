# TASK-7.7: Spouse Career History & Pension

**Status:** TODO
**Sprint:** 7
**Priority:** P1 (high)
**Est. effort:** 2.5 hr
**Dependencies:** TASK-7.4, TASK-6.1, TASK-6.2

---

## Context

The spouse needs their own career history and pension estimate, using the same tables and engine as the primary user. A spouse who was CDI for 15 years before becoming conjointe collaboratrice has 60 validated trimestres from the régime général — this dramatically affects projected retirement income.

---

## Step-by-Step Instructions

### Step 1: Add `owner` column to career_periods

File: `backend/app/models/career.py`

Add a column to distinguish user vs spouse career periods:

```python
owner = Column(String(10), nullable=False, server_default="user")
# Values: "user" or "spouse"
```

Create migration:
```bash
alembic revision --autogenerate -m "add owner column to career_periods"
alembic upgrade head
```

### Step 2: Update career router to support owner filter

File: `backend/app/routers/career.py`

Add `owner` query parameter to list and summary endpoints:

```python
@router.get("", response_model=list[CareerPeriodRead])
async def list_career_periods(
    owner: str = Query(default="user", regex="^(user|spouse)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(CareerPeriod).where(
        CareerPeriod.user_id == str(current_user.id),
        CareerPeriod.owner == owner,
    ).order_by(CareerPeriod.start_date)
    # ...
```

Do the same for `GET /api/career/summary?owner=spouse`.

Update `POST /api/career` to accept `owner` in the request body (default "user").

### Step 3: CC trimestre calculation

Conjointe collaboratrice generates pension rights based on the chosen cotisation option. Add to the pension engine:

File: `backend/app/calculations/pension.py`

```python
def estimate_cc_trimestres_per_year(cc_option: str, user_ca: Decimal) -> int:
    """CC validates trimestres based on cotisation base vs SMIC threshold.
    
    If the annual cotisation base >= 600 * SMIC horaire (~6,990€/year in 2024),
    the CC earns 4 trimestres. Otherwise proportional.
    """
    PLAFOND_SS = Decimal("46368")
    SMIC_TRIM_THRESHOLD = Decimal("6990")
    
    bases = {
        "tiers_plafond": PLAFOND_SS / 3,
        "moitie_plafond": PLAFOND_SS / 2,
        "tiers_revenu": user_ca / 3,
        "moitie_revenu": user_ca / 2,
    }
    base = bases.get(cc_option, Decimal("0"))
    if base >= SMIC_TRIM_THRESHOLD * 4:
        return 4
    return min(4, int(base / SMIC_TRIM_THRESHOLD))
```

### Step 4: Combined pension endpoint

Extend `GET /api/projection/pension-estimate` to include spouse pension:

```python
# In the response:
{
    "user_pension": {
        "total_monthly": "850.00",
        "trimestres_validated": 144,
        "trimestres_required": 172,
        "has_taux_plein": false,
        # ... existing fields
    },
    "spouse_pension": {
        "total_monthly": "620.00",
        "trimestres_validated": 98,
        "trimestres_required": 172,
        "has_taux_plein": false,
        "includes_cc_trimestres": 12,
    },
    "household_pension_monthly": "1470.00"
}
```

To compute spouse pension:
1. Fetch spouse career periods (`owner=spouse`)
2. If spouse is CC: add CC trimestres for each projected year from now to retirement
3. Feed into the same `estimate_pension()` function used for the user
4. Sum both for household total

### Step 5: Update career schema

File: `backend/app/schemas/career.py`

Add `owner` field to `CareerPeriodCreate` and `CareerPeriodRead`:
```python
owner: str = Field(default="user", pattern="^(user|spouse)$")
```

### Step 6: Unit tests

Add to `backend/tests/test_career.py` (or create `test_spouse_career.py`):
- Test creating career period with `owner=spouse`
- Test filtering by owner
- Test CC trimestre calculation for each option
- Test combined pension endpoint returns both user and spouse
- Test spouse with mixed career (CDI + CC periods)

---

## SCOPE BOUNDARY

- DO NOT build the frontend for spouse career. That's TASK-7.9.
- DO NOT modify the projection engine yet. That's TASK-7.8.
- DO NOT compute pension for cases with no spouse (backward compat — `spouse_pension` is null).
- DO NOT model pension complémentaire separately for CC (simplified: included in the CC rate).
- Expected change: ~30 lines model, ~40 lines router, ~30 lines pension engine, ~60 lines tests.

## DONE WHEN

- [ ] `owner` column added to career_periods table
- [ ] Career endpoints filter by `?owner=user|spouse`
- [ ] CC trimestre calculation returns correct values for all 4 options
- [ ] Pension endpoint returns `spouse_pension` when spouse + career periods exist
- [ ] Pension endpoint returns `household_pension_monthly` sum
- [ ] Backward compat: no spouse → `spouse_pension` is null
- [ ] All tests pass
