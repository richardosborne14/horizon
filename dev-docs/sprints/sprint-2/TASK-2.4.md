# TASK-2.4: CAF Auto-Estimation Service

**Status:** BACKLOG
**Sprint:** 2
**Priority:** P1 (high)
**Est. effort:** 1 hr
**Dependencies:** TASK-2.1

## Context

French families with 2+ children under 20 receive allocations familiales from the CAF. The amount depends on number of qualifying children and household income. Now that we have the life entity model (with kids and their birth dates), we can auto-estimate CAF for users who haven't entered a manual override.

The estimation is intentionally approximate — CAF rules are Byzantine and change yearly. We provide a reasonable ballpark that the user can override with their real amount.

## Requirements

1. Create `backend/app/calculations/caf.py`:

```python
def estimate_monthly_caf(
    kids: list[dict],       # [{"birth_date": date, ...}]
    reference_year: int,
    annual_household_income: Decimal,
) -> Decimal:
    """
    Estimate monthly CAF allocations familiales.
    
    2026 base rates (revalorised ~1.5%/year):
    - 2 children: ~148€/month
    - 3 children: ~338€/month  
    - 4+ children: ~338€ + ~190€ per additional child
    
    Income-tested: above ~70k€ + 5k€/child, amount halved.
    Above ~93k€ + 5k€/child, amount quartered.
    
    Children qualify until age 20 (not 18).
    """
```

2. Function `estimate_caf_for_year(user_id, year, db) -> Decimal`:
   - Counts kids under 20 as of January 1st of that year (from life_entities)
   - Gets user's projected income for that year (gross CA from profile × growth rate)
   - Returns monthly CAF estimate
   - Returns `Decimal("0")` if < 2 qualifying kids

3. Function `get_caf_timeline(user_id, from_year, to_year, db) -> list[dict]`:
   - For each year, computes: `{"year": int, "qualifying_kids": int, "monthly_amount": Decimal}`
   - Shows CAF tapering as kids age past 20
   - Revalorises base amounts at ~1.5%/year

4. API endpoint `GET /api/profile/caf-estimate?from_year=2026&to_year=2056`:
   - Returns the timeline
   - Used by the Expenses section and the projection engine

5. Integration: if `profile.caf_override_monthly` is null, the projection engine (Sprint 4) uses this estimate. If set, uses the override (still adjusted for kid aging).

6. Unit tests:
   - 2 kids under 20, income < 70k → full rate
   - 2 kids under 20, income > 93k → quarter rate
   - Kid turns 20 in 2035 → qualifying count drops
   - 0 or 1 kid → returns 0

## Technical Approach

### Files to Create
- `backend/app/calculations/caf.py`
- `backend/app/routers/profile.py` — add CAF estimate endpoint
- `backend/tests/test_caf.py`

### Simplifications
- We use a two-tier income test (full / half / quarter) rather than the actual 3-tier sliding scale. Close enough for 30-year planning.
- Base rates are hardcoded for 2026 and revalorised at 1.5%/year. Actual revalorisation varies but 1.5% is a reasonable long-term average.
- We check kid age as of January 1st of each year for simplicity.

## Acceptance Criteria

- [ ] 2 kids aged 5 and 8, income 50k → ~148€/month (2026 base)
- [ ] 3 kids → ~338€/month
- [ ] High income (> 93k) → reduced amount
- [ ] 1 kid → 0€
- [ ] Timeline shows CAF dropping when oldest kid turns 20
- [ ] API returns correct timeline
- [ ] Unit tests cover income tiers and kid aging
- [ ] LEARNINGS.md updated

## Notes

- This is a rough estimate, clearly labeled as such in the UI. The Expenses section hint says "estimation basée sur vos enfants et revenus — saisissez votre montant réel si vous le connaissez."
- The projection engine will use this per-year (CAF in 2026 may differ from CAF in 2035 as kids age out).
- Complement de libre choix (PAJE) for young children is NOT included — it's too variable (depends on employment status, childcare type, etc.). Users can add it via the CAF override.
