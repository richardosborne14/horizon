# HOTFIX-5: MacBook Air (2024) Missing Annual Cost Events

**Severity:** MEDIUM (data gap — running costs for one asset are invisible to projection)  
**Discovered:** 2026-05-12 via DB audit

## Problem

The MacBook Air (2024) life entity (entity age = 2 at projection start) has only replacement cost events (`t-replace-1` through `t-replace-10`). It is missing:

- `t-accessories` — Accessoires / Réparations: **100€/year**, from age 0 to age 30
- `t-insurance` — Assurance / Garantie étendue: **100€/year**, from age 0 to age 3

The MacBook Air (2021) entity has both of these correctly. The asymmetry indicates the annual events were accidentally deleted when the 2024 entity was edited. The result: the 2024 MacBook has zero modelled running costs, silently understating tech expenses by ~100€/year (insurance period is nearly over at entity age 2, so that's minor; the accessories at 100€/year for ~28 remaining years is the real gap).

---

## Root Cause

Life entity cost events are stored per-entity. When the user edited the MacBook (2024) entity (likely to adjust replacement amounts), the edit operation replaced all cost events with only what was in the form, discarding the annual events that weren't explicitly shown. This is a known editing UX risk flagged in the Sprint 6 audit.

---

## Fix

### Part A — Insert the missing cost events for MacBook (2024)

Identify the MacBook Air (2024) entity ID from the `life_entities` table:
```sql
SELECT id FROM life_entities 
WHERE user_id = '67b56986-89c3-4ff5-808e-d3177507d341'
  AND name ILIKE '%macbook%2024%'
  AND is_active = true;
```

Then insert the two missing cost event rows. Use the same structure as the equivalent events on the 2021 MacBook:

```sql
-- t-accessories: 100€/year, age 0-30, annual
INSERT INTO life_entity_cost_events 
  (entity_id, event_key, label, from_age, to_age, amount, frequency)
VALUES
  ('<2024_macbook_id>', 't-accessories', 'Accessoires / Réparations', 0, 30, 100.00, 'annual'),
  ('<2024_macbook_id>', 't-insurance',   'Assurance / Garantie étendue', 0, 3, 100.00, 'annual');
```

Since entity age at projection start is 2, `t-insurance` (age 0–3) will fire for 1 more year (2027), then expire. `t-accessories` (age 0–30) will run for 28 more years. Both are correct behaviour.

### Part B — Add a data integrity guard to the cost event save handler

When the user saves a life entity's cost events via the UI, the backend replaces all existing events with the submitted set. This is the mechanism that caused the loss. Add a guard:

Before replacing events, check if the entity type has a known set of default event keys (e.g., for `type='tech'`: `['t-accessories', 't-insurance', 't-replace-1', ...]`). If any default keys are absent from the submitted set, do NOT silently drop them. Instead either:

**Option A (recommended):** Re-merge the missing defaults back in before saving. Any event key present in defaults but absent from the submission gets re-added at its default amount. Custom events (added by user) are preserved as-is.

**Option B:** Show the user a warning: "You are removing standard events: t-accessories, t-insurance. Are you sure?" and require confirmation.

Implement Option A. It requires ~20 lines in the save handler: load default events for entity type, compare keys, merge missing ones back before the DB write.

---

## SCOPE BOUNDARY

**DO NOT:**
- Change the replacement event amounts or schedule for the 2024 MacBook
- Modify the 2021 MacBook entity at all
- Rebuild the life entity editing UI
- Add new cost event types or categories

**ONLY:**
- Insert 2 missing cost event rows for the 2024 MacBook entity
- Add the default-event merge guard to the life entity save handler

Estimated change: 2 SQL inserts + ~20 lines in save handler.

---

## Verification

1. **DB check:** MacBook (2024) entity now has `t-accessories` and `t-insurance` events
2. **Vie tab → Tech section:** MacBook (2024) shows annual cost events alongside replacement events
3. **Projection:** Tech expenses increase by ~100€/year for years where entity age 0–30 (i.e. all remaining years)
4. **Edit test:** Open MacBook (2024) in Vie tab, save without changes → verify both annual events are still present afterwards (the guard works)
5. **MacBook (2021) unchanged** — no regressions

---

## DONE WHEN

- [ ] `t-accessories` (100€/year, age 0–30) exists for MacBook (2024) in DB
- [ ] `t-insurance` (100€/year, age 0–3) exists for MacBook (2024) in DB
- [ ] Projection shows increased tech costs (~100€/year) for this entity going forward
- [ ] Life entity save handler merges default events back if missing from submitted set
- [ ] Edit-and-save round-trip preserves annual events (regression test)
