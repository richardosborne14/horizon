# TASK-2.3: RecurringExpense Model & API

**Status:** BACKLOG
**Sprint:** 2
**Priority:** P1 (high)
**Est. effort:** 1 hr
**Dependencies:** TASK-1.1

## Context

Expenses that recur annually but have a defined start and end year — loan repayments, annual holiday budget, kid's sports club subscription, a car lease. These don't fit the life entity model (they're not "things" with ages) but they're not permanent monthly expenses either. They're time-bounded annual costs.

## Requirements

1. Create `backend/app/models/recurring_expense.py`:

```python
class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"

    id            = Column(UUID, primary_key=True, default=uuid4)
    user_id       = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    label         = Column(String(200), nullable=False)
    annual_amount = Column(Numeric(10, 2), nullable=False)
    from_year     = Column(Integer, nullable=False)
    to_year       = Column(Integer, nullable=False)
    category      = Column(String(50), nullable=True)  # optional grouping
    is_active     = Column(Boolean, nullable=False, server_default="true")
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

2. Pydantic schemas:
   - `RecurringExpenseCreate`: label, annual_amount (>= 0), from_year, to_year (>= from_year)
   - `RecurringExpenseRead`: all fields
   - `RecurringExpenseUpdate`: all optional

3. CRUD router `backend/app/routers/recurring_expenses.py`:
   - `GET /api/recurring-expenses` — list for user
   - `POST /api/recurring-expenses` — create
   - `PUT /api/recurring-expenses/{id}` — update
   - `DELETE /api/recurring-expenses/{id}` — soft delete

4. Alembic migration

5. Validation: `to_year >= from_year`, `annual_amount >= 0`

## Technical Approach

### Files to Create
- `backend/app/models/recurring_expense.py`
- `backend/app/schemas/recurring_expense.py`
- `backend/app/routers/recurring_expenses.py`
- `backend/app/models/__init__.py` — add import
- `backend/app/main.py` — mount router
- `backend/alembic/versions/xxxx_add_recurring_expenses.py`
- `backend/tests/test_recurring_expenses.py`

## Acceptance Criteria

- [ ] Migration creates table
- [ ] CRUD endpoints work with auth
- [ ] Validation rejects `to_year < from_year` and negative amounts
- [ ] User scoping (A can't see B's expenses)
- [ ] Unit tests pass
- [ ] LEARNINGS.md updated

## Notes

- The projection engine (Sprint 4) queries this table per year: `SELECT SUM(annual_amount) WHERE from_year <= :year AND to_year >= :year AND user_id = :uid AND is_active = true`
- Common examples to seed in frontend hints: "Remboursement prêt auto" (2026→2030, 3600€/an), "Vacances d'été" (2026→2055, 3000€/an), "Sport enfant" (2026→2034, 500€/an)
