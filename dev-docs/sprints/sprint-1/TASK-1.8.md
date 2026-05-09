# TASK-1.8: Sidebar Quick Stats (Live Data)

**Status:** BACKLOG
**Sprint:** 1
**Priority:** P2 (medium)
**Est. effort:** 1 hr
**Dependencies:** TASK-1.1, TASK-1.2, TASK-1.4

## Context

The sidebar nav (built in TASK-0.3) has a "Quick Stats" panel below the navigation items that shows placeholder dashes. This task wires it to real data from the user's profile so the sidebar always reflects the current state: CA/mois, number of kids, monthly savings allocation, and number of investment projects.

This is a small polish task that makes the app feel alive — you change your CA on the Revenue page and the sidebar updates immediately.

**Prototype reference:** `horizon30.jsx` → sidebar `Aperçu` panel below nav items. Four key-value rows in 10px text.

## Requirements

1. Create a lightweight API endpoint `GET /api/profile/summary`:
   - Returns a compact summary object:
   ```json
   {
     "monthly_gross_ca": 5000,
     "kid_count": 2,
     "monthly_savings_total": 950,
     "investment_project_count": 1
   }
   ```
   - `kid_count` = count of LifeEntity where `entity_type = "kid"` and `is_active = true` (returns 0 if table doesn't exist yet — Sprint 0 has no life entities table)
   - `monthly_savings_total` = sum of all InvestmentAllocation `monthly_contribution` (returns 0 if table doesn't exist yet)
   - `investment_project_count` = count of Project where `type = "invest"` and `is_active = true` (returns 0 if table doesn't exist yet)
   - The endpoint should gracefully return zeros for data that doesn't exist yet (Sprint 2/3 models)

2. Update `frontend/src/routes/(app)/+layout.svelte`:
   - Fetch summary on layout mount
   - Display in sidebar quick stats panel:
     - CA/mois → `formatCurrency(summary.monthly_gross_ca, 0)`
     - Enfants → `summary.kid_count`
     - Épargne/m → `formatCurrency(summary.monthly_savings_total, 0)` in teal
     - Projets → `summary.investment_project_count`
   - Re-fetch when navigating between sections (or use a Svelte store that profile-editing pages invalidate)

3. **Reactivity approach**: Create a `profileSummary` Svelte store. When any section saves profile data, it calls `invalidateSummary()` which triggers a re-fetch. The layout subscribes to this store.

4. Add age→target display in header: "40 → 70 ans • 30 ans de runway" — computed from profile data.

## Technical Approach

### Files to Create/Modify
- `backend/app/routers/profile.py` — add `GET /api/profile/summary`
- `frontend/src/routes/(app)/+layout.svelte` — wire up stats
- `frontend/src/routes/(app)/+layout.server.ts` — load summary in layout data
- `frontend/src/lib/stores/profile-summary.ts` — reactive store for invalidation
- `frontend/src/locales/fr.json` — add `sidebar.*` keys if not already present

### Graceful Degradation
The summary endpoint MUST NOT fail if Sprint 2/3 tables don't exist yet. Use try/except or check table existence:

```python
async def get_summary(user_id: UUID, db: AsyncSession) -> dict:
    profile = await get_or_create_profile(user_id, db)
    
    kid_count = 0
    savings_total = Decimal("0")
    project_count = 0
    
    # These will work once Sprint 2/3 models exist
    try:
        kid_count = await db.scalar(
            select(func.count()).where(
                LifeEntity.user_id == user_id,
                LifeEntity.entity_type == "kid",
                LifeEntity.is_active == True,
            )
        )
    except Exception:
        pass  # Table doesn't exist yet
    
    # Similar for savings and projects...
    
    return {
        "monthly_gross_ca": float(profile.monthly_gross_ca or 0),
        "kid_count": kid_count,
        "monthly_savings_total": float(savings_total),
        "investment_project_count": project_count,
    }
```

## Acceptance Criteria

- [ ] `GET /api/profile/summary` returns correct data for current user
- [ ] Sidebar shows CA/mois from profile
- [ ] Sidebar shows "0" for kids/savings/projects (Sprint 2/3 not built yet)
- [ ] Changing CA on Revenue page → sidebar updates without full page reload
- [ ] Header shows "40 → 70 ans • 30 ans de runway" (from profile birth_date and target_retirement_age)
- [ ] New user with no profile → sidebar shows dashes or zeros gracefully
- [ ] Endpoint doesn't error if Sprint 2/3 tables don't exist
- [ ] All sidebar text via i18n keys
- [ ] LEARNINGS.md updated

## Notes

- This is the first task that touches the layout after TASK-0.3. Be careful not to break the sidebar nav structure.
- The invalidation pattern is important to get right early — it'll be used by every section that saves data. Keep it simple: a writable store with a `tick` counter, layout watches it.
- The "age → target • N years of runway" header display requires `birth_date` to be set. If null, show just "Horizon 30" without the age range. Nudge the user: "Renseignez votre date de naissance dans Identité."
- Kid count, savings, and project count will start showing real data as Sprint 2 and 3 are completed — no additional wiring needed because the endpoint already queries those tables.
