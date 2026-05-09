# TASK-4.2: Projection API Endpoint

**Status:** BACKLOG
**Sprint:** 4
**Priority:** P0 (critical)
**Est. effort:** 1 hr
**Dependencies:** TASK-4.1

## Context

The bridge between the database and the projection engine. Reads all user data (profile, life entities, recurring expenses, investments, projects), assembles a `ProjectionInput`, calls the engine, and returns the timeline plus summary statistics. This is the single endpoint the Runway frontend calls.

## Requirements

1. Create `backend/app/routers/projection.py`:

   **`GET /api/projection?scale=moderate`**
   - Auth required
   - Query param: `scale` (default "moderate") — overrides profile.world_scale for this request
   - Assembles `ProjectionInput` from:
     - UserProfile (age, CA, growth, expenses, tax breaks, CAF, status change, goal)
     - LifeEntities (all active, with cost_events)
     - RecurringExpenses (all active)
     - InvestmentAllocations (all 7 vehicles)
     - Projects (all active)
   - Calls `project_timeline(input)` 
   - Returns:

```json
{
  "timeline": [...],  // list of YearProjection
  "summary": {
    "years": 30,
    "final_wealth": "485230.00",
    "final_passive_monthly": "1617.43",
    "total_invested": "342000.00",
    "total_returns": "143230.00",
    "goal_year": {"year": 2049, "age": 63},  // or null
    "milestones": [
      {"label": "100k€", "year": 2035, "age": 49},
      {"label": "250k€", "year": 2042, "age": 56}
    ]
  },
  "scale": "moderate"
}
```

2. **Data assembly helper** `_assemble_input(user_id, scale, db) -> ProjectionInput`:
   - Single async function that runs all DB queries in parallel where possible
   - Computes `current_age` from profile.birth_date
   - Computes entity ages from reference_date
   - Extracts kids' birth dates for CAF
   - Resolves growth rate from preset
   - Falls back gracefully: no profile → error; no entities → empty lists; no allocations → zeros

3. **Error handling:**
   - No profile → 404 with message "Complétez votre profil d'abord"
   - No birth_date → 422 with message "Date de naissance requise pour la projection"
   - Engine error → 500 with logged traceback

4. **Performance:** Target < 500ms. The DB queries are the bottleneck, not the engine. Use `asyncio.gather` for parallel queries. Log response time.

5. **No caching for MVP.** The projection is fast enough without caching, and invalidation is complex (any profile/entity/allocation change would bust the cache). Add caching later if needed.

## Technical Approach

### Files to Create
- `backend/app/routers/projection.py`
- `backend/app/schemas/projection.py` — response models
- `backend/app/main.py` — mount router
- `backend/tests/test_projection_api.py`

### Parallel DB Queries
```python
async def _assemble_input(user_id: UUID, scale: str, db: AsyncSession) -> ProjectionInput:
    profile, entities, recurring, allocations, projects = await asyncio.gather(
        get_profile(user_id, db),
        get_active_entities(user_id, db),
        get_active_recurring(user_id, db),
        get_all_allocations(user_id, db),
        get_active_projects(user_id, db),
    )
    # ... assemble ProjectionInput from results
```

## Acceptance Criteria

- [ ] `GET /api/projection?scale=moderate` returns timeline + summary
- [ ] Response includes all YearProjection fields
- [ ] Milestones computed and returned
- [ ] Goal year returned (or null)
- [ ] Scale parameter overrides profile default
- [ ] 404 if no profile exists
- [ ] 422 if birth_date is null
- [ ] Response time < 500ms (logged)
- [ ] Parallel DB queries (verified in logs)
- [ ] Integration test: create full profile + entities + allocations → call projection → verify non-empty timeline
- [ ] LEARNINGS.md updated

## Notes

- This endpoint will be called every time the user changes the scale selector or refreshes the Runway page. It should be fast and stateless.
- The `scale` query param lets the frontend override the profile's saved scale for quick comparison without saving. The frontend also saves the selected scale to the profile for persistence.
- Decimal values serialize as strings in JSON. The frontend must parse them. Use a consistent format: `"1234.56"` not `"1,234.56"`.
