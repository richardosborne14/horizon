# TASK-1.2: AE Cotisation Rate Engine

**Status:** BACKLOG
**Sprint:** 1
**Priority:** P0 (critical)
**Est. effort:** 1 hr
**Dependencies:** None

## Context

AE cotisation rates are NOT flat over a 30-year projection. They've been increasing due to legislative changes and are projected to continue. Richard currently pays ~26.2% (BNC + VL) and it's set to go up. The projection engine needs a time-dependent rate lookup that returns different rates for different future years. This is one of the most important accuracy features — getting this wrong compounds over 30 years.

The rates include: URSSAF base + versement libératoire IR (~2.2%) + formation professionnelle + CFP. The schedule is stored in code (not DB) because changes need code review, not a UI toggle.

## Requirements

1. Create `backend/app/calculations/ae_rates.py`:

```python
from decimal import Decimal

# Rate schedules: URSSAF + VL + formation + CFP combined
# Sources: URSSAF published rates + legislative trend projections
# Updated annually — flag in LEARNINGS.md when rates change
AE_RATE_SCHEDULE: dict[str, list[dict]] = {
    "bnc_non_reglementee": [
        {"from_year": 2024, "rate": Decimal("0.245")},
        {"from_year": 2025, "rate": Decimal("0.252")},
        {"from_year": 2026, "rate": Decimal("0.262")},
        {"from_year": 2027, "rate": Decimal("0.268")},  # projected
        {"from_year": 2028, "rate": Decimal("0.275")},  # projected
        {"from_year": 2030, "rate": Decimal("0.285")},  # projected
        {"from_year": 2035, "rate": Decimal("0.295")},  # projected
    ],
    "bic_services": [
        {"from_year": 2024, "rate": Decimal("0.218")},
        {"from_year": 2025, "rate": Decimal("0.224")},
        {"from_year": 2026, "rate": Decimal("0.237")},
        {"from_year": 2028, "rate": Decimal("0.245")},
        {"from_year": 2030, "rate": Decimal("0.255")},
        {"from_year": 2035, "rate": Decimal("0.265")},
    ],
    "bic_vente": [
        {"from_year": 2024, "rate": Decimal("0.132")},
        {"from_year": 2026, "rate": Decimal("0.148")},
        {"from_year": 2028, "rate": Decimal("0.155")},
        {"from_year": 2030, "rate": Decimal("0.162")},
    ],
    "bnc_cipav": [
        {"from_year": 2024, "rate": Decimal("0.232")},
        {"from_year": 2026, "rate": Decimal("0.254")},
        {"from_year": 2028, "rate": Decimal("0.262")},
        {"from_year": 2030, "rate": Decimal("0.272")},
    ],
}
```

2. Implement functions:
   - `get_ae_rate(activity_type: str, year: int) -> Decimal` — walks the schedule, returns the rate effective for that year (latest entry where `from_year <= year`)
   - `get_rate_schedule(activity_type: str) -> list[dict[str, Any]]` — returns the full schedule for frontend display
   - `get_all_schedules() -> dict[str, list[dict]]` — returns all schedules (for rate comparison UI)
   - `compute_annual_charges(gross_annual: Decimal, activity_type: str, year: int) -> dict` — returns `{"rate": Decimal, "urssaf": Decimal, "cfe": Decimal, "total": Decimal}`

3. CFE (Cotisation Foncière des Entreprises):
   - Flat estimate: ~300€/year in 2026, inflation-adjusted
   - `get_cfe_estimate(year: int, inflation_rate: Decimal = Decimal("0.025")) -> Decimal`

4. Create API router `backend/app/routers/rates.py`:
   - `GET /api/rates/ae-schedule?type=bnc_non_reglementee` — returns schedule for one type
   - `GET /api/rates/ae-schedules` — returns all schedules
   - `GET /api/rates/ae-rate?type=bnc_non_reglementee&year=2030` — returns single rate
   - No auth required (public reference data)

5. Unit tests in `backend/tests/test_ae_rates.py`:
   - Known 2026 rates for all 4 types
   - Rate lookup for past year (returns earliest applicable)
   - Rate lookup for far future year (returns latest applicable)
   - `compute_annual_charges` for a known gross amount

## Technical Approach

### Files to Create
- `backend/app/calculations/ae_rates.py`
- `backend/app/routers/rates.py`
- `backend/tests/test_ae_rates.py`
- `backend/app/main.py` — mount router

### Key Design Decision
Rates are in code, not the database, because:
1. They're reference data that affects financial accuracy
2. Changes should go through code review (git history)
3. Projections beyond published rates are estimates that need human judgment
4. The rate schedule is small (< 30 entries total)

## Acceptance Criteria

- [ ] `get_ae_rate("bnc_non_reglementee", 2026)` returns `Decimal("0.262")`
- [ ] `get_ae_rate("bnc_non_reglementee", 2029)` returns `Decimal("0.275")` (2028 entry applies)
- [ ] `get_ae_rate("bnc_non_reglementee", 2050)` returns `Decimal("0.295")` (latest entry)
- [ ] `compute_annual_charges(Decimal("60000"), "bnc_non_reglementee", 2026)` returns correct breakdown
- [ ] API endpoints return correct JSON
- [ ] All unit tests pass
- [ ] No float anywhere — all Decimal
- [ ] LEARNINGS.md updated

## Notes

- The projected rates (2027+) are educated estimates based on legislative trends. They should be reviewed annually and updated when actual rates are published. Add a comment in the code: `# REVIEW ANNUALLY: update projected rates when URSSAF publishes new schedule`
- Rates WITHOUT versement libératoire would be ~2.2% lower. For MVP we assume VL is on (it's on the profile). A future enhancement could compute both and show the delta.
- ComCoi's `calc_ae_urssaf_cotisations` in `social_charges.py` is a reference — check it for the ACRE logic pattern if we add ACRE support later.
