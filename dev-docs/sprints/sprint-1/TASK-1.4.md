# TASK-1.4: Monthly Expense Schema

**Status:** BACKLOG
**Sprint:** 1
**Priority:** P0 (critical)
**Est. effort:** 1 hr
**Dependencies:** TASK-1.1

## Context

Monthly expenses are stored as JSONB on the UserProfile (defined in TASK-1.1). This task adds proper Pydantic validation, default expense categories, and a dedicated API sub-route for updating expenses independently of the full profile. The expense data is the base for inflation projections — users enter 2026 values, the engine applies compounding.

## Requirements

1. Define expense schema in `backend/app/schemas/profile.py`:

```python
EXPENSE_CATEGORIES = [
    "loyer", "energie", "internet", "assurance", "transport",
    "alimentation", "sante", "loisirs", "abonnements",
    "impots", "credit", "divers",
]

class MonthlyExpenses(BaseModel):
    loyer: Decimal = Decimal("0")
    energie: Decimal = Decimal("0")
    internet: Decimal = Decimal("0")
    assurance: Decimal = Decimal("0")
    transport: Decimal = Decimal("0")
    alimentation: Decimal = Decimal("0")
    sante: Decimal = Decimal("0")
    loisirs: Decimal = Decimal("0")
    abonnements: Decimal = Decimal("0")
    impots: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    divers: Decimal = Decimal("0")

    @validator("*", pre=True)
    def non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Expense values must be >= 0")
        return v

    @property
    def total(self) -> Decimal:
        return sum(getattr(self, f) for f in EXPENSE_CATEGORIES)
```

2. Add `PUT /api/profile/expenses` endpoint:
   - Accepts `MonthlyExpenses` body
   - Updates only the `monthly_expenses` JSONB column
   - Returns updated expenses + computed `total`

3. Add `GET /api/profile/expenses` endpoint:
   - Returns current expenses + `total`

4. Add expense category labels (French) to the constants API or as part of the response:
```python
EXPENSE_LABELS = {
    "loyer": "Loyer / Crédit immobilier",
    "energie": "Énergie (élec, gaz)",
    "internet": "Internet & téléphone",
    "assurance": "Assurances personnelles",
    "transport": "Carburant / Transport",
    "alimentation": "Alimentation",
    "sante": "Santé / Mutuelle",
    "loisirs": "Loisirs & sorties",
    "abonnements": "Abonnements",
    "impots": "Impôts locaux",
    "credit": "Crédits en cours",
    "divers": "Divers",
}
```

5. Add inflation preview helper in `backend/app/calculations/expenses.py`:
```python
def preview_inflation(monthly_total: Decimal, scales: dict, horizons: list[int] = [5, 10, 20, 30]) -> dict:
    """For each scale × horizon, compute inflated monthly total."""
    # Returns: {"optimistic": {"5": Decimal, "10": Decimal, ...}, "moderate": {...}, ...}
```

6. Add `GET /api/profile/expenses/inflation-preview` — returns the preview grid for the frontend table

7. Unit tests: validation (reject negative), total computation, inflation preview math

## Technical Approach

### Files to Create/Modify
- `backend/app/schemas/profile.py` — add MonthlyExpenses, EXPENSE_CATEGORIES, EXPENSE_LABELS
- `backend/app/routers/profile.py` — add expense sub-endpoints
- `backend/app/calculations/expenses.py` — inflation preview helper
- `backend/tests/test_expenses.py`

## Acceptance Criteria

- [ ] `PUT /api/profile/expenses` saves and returns expenses with total
- [ ] Negative values rejected with 422
- [ ] Total computed correctly (sum of all 12 categories)
- [ ] Inflation preview returns correct values for all 3 scales × 4 horizons
- [ ] `800 * (1.03)^10 = 1074.81` (moderate, 10 years, loyer) — verify math
- [ ] Labels returned for frontend display
- [ ] Unit tests pass
- [ ] LEARNINGS.md updated

## Notes

- Expenses are deliberately stored as flat JSONB rather than a separate table. At this stage there's no monthly variation — the user enters their 2026 baseline and the projection engine handles the rest. Monthly tracking (like ComCoi's monthly reports) is a potential future feature but not MVP.
- The inflation preview is a read-only computation — it doesn't store anything. The frontend calls it to render the preview table in the Expenses section.
