# HOTFIX-6: Database Cleanup — Inactive Duplicate Entities + Test Recurring Expense

**Severity:** LOW (no calculation impact — data hygiene)  
**Discovered:** 2026-05-12 via DB audit  
**Safe to run independently at any time**

## Problem

Two categories of inert data clutter the database:

### Issue A — 5 inactive duplicate life entity rows
The DB contains 5 rows with `is_active = false` for entities that have live counterparts:
- 4 duplicate rows for **Ellie** (born 2015-07-02)
- 1 duplicate row for **Saoirse** (born 2018-03-25)

These were created when the user edited these entities multiple times and old rows were not cleaned up. They are not used in any calculation (`is_active = false`), but they:
- Pollute the `life_entities` table
- Could cause confusion in future queries that forget to filter `is_active`
- Will accumulate over time if not addressed

### Issue B — Test/stub recurring expense
The `recurring_expenses` table contains one row:
- Label: "Nouvelle dépense"
- Amount: **19€/year**
- From: 2026, To: 2031
- Category: none

This appears to be a test entry created during development (the default label "Nouvelle dépense" is likely the placeholder text, not a real expense name). 19€/year is not a meaningful amount. It has no category and no description.

---

## Fix

### Part A — Delete inactive duplicate entity rows

**Step 1:** Confirm what will be deleted. Run this SELECT first and verify the output before executing any DELETE:

```sql
SELECT id, name, type, reference_date, is_active, created_at
FROM life_entities
WHERE user_id = '67b56986-89c3-4ff5-808e-d3177507d341'
  AND is_active = false
ORDER BY name, created_at;
```

Expected output: 5 rows — 4 Ellie variants + 1 Saoirse. Confirm all 5 are `is_active = false`. Confirm the active Ellie and active Saoirse rows still exist with `is_active = true`.

**Step 2:** Check for orphaned cost events on the inactive rows. The inactive entity rows may have their own `life_entity_cost_events` rows (confirmed in the audit — the inactive Ellie rows have a DIFFERENT set of cost events than the active one). Delete cost events for inactive entities first:

```sql
DELETE FROM life_entity_cost_events
WHERE entity_id IN (
  SELECT id FROM life_entities
  WHERE user_id = '67b56986-89c3-4ff5-808e-d3177507d341'
    AND is_active = false
);
```

**Step 3:** Delete the inactive entity rows:

```sql
DELETE FROM life_entities
WHERE user_id = '67b56986-89c3-4ff5-808e-d3177507d341'
  AND is_active = false;
```

Verify: `SELECT COUNT(*) FROM life_entities WHERE user_id = '67b56986...'` should return **8** (the 8 active entities documented in the audit).

### Part B — Handle the "Nouvelle dépense" recurring expense

Do NOT automatically delete it. The user may have intended it for something. Instead:

**Option 1 (preferred):** Flag it in the UI as requiring attention. Add a visual indicator in the recurring expenses list when an expense has the default placeholder label "Nouvelle dépense" — e.g., a yellow warning dot and tooltip: "Cette dépense n'a pas encore été nommée. Mettez-la à jour ou supprimez-la."

**Option 2:** Add server-side validation that rejects saving a recurring expense with the default placeholder label, prompting the user to enter a real name.

Implement Option 1. It requires ~5 lines in the recurring expenses list component.

The 19€/year amount will remain in calculations until the user deletes it, which is correct — it's their data to manage.

### Part C — Add a guard against future inactive row accumulation

Find the life entity update/edit handler. When a user edits a life entity, confirm the pattern is:
- **If editing in-place:** UPDATE the existing row, do not create a new row
- **If the pattern is "insert new + deactivate old":** add a cleanup step that deletes (not just deactivates) the old row after the new one is confirmed saved

If the current pattern is "insert new + deactivate old" without cleanup, change the deactivate to a delete (after verifying no foreign key constraints block it — cost events are child rows, so delete those first).

---

## SCOPE BOUNDARY

**DO NOT:**
- Touch any `is_active = true` entity rows
- Delete recurring expenses on behalf of the user
- Modify the active Ellie or Saoirse cost events
- Run any DELETE without first running the corresponding SELECT to confirm scope

**ONLY:**
- Delete 5 inactive entity rows and their orphaned cost events
- Add a UI flag for placeholder-named recurring expenses
- Fix the entity edit handler to clean up old rows instead of deactivating them

Estimated change: 3 SQL statements + ~10 lines in UI + ~5 lines in entity save handler.

---

## Verification

1. **DB check:** `SELECT COUNT(*) FROM life_entities WHERE user_id = '67b56986...'` → **8** (was 13)
2. **DB check:** No orphaned rows in `life_entity_cost_events` for deleted entity IDs
3. **Vie tab:** Only 8 entities visible — Romy, Ellie, Saoirse, Layla, MacBook 2021, MacBook 2024, Xsara, Peugeot
4. **Recurring expenses list:** "Nouvelle dépense" entry shows a yellow warning indicator
5. **Edit Ellie test:** Edit Ellie, save → only 1 active row for Ellie afterwards (no new inactive row created)
6. **Projection output unchanged** — all 8 active entities still fire correctly

---

## DONE WHEN

- [ ] 5 inactive `life_entities` rows deleted
- [ ] Orphaned `life_entity_cost_events` rows for deleted entities deleted
- [ ] `life_entities` count for this user = 8
- [ ] "Nouvelle dépense" recurring expense shows placeholder warning in UI
- [ ] Entity edit handler deletes old row rather than deactivating it
- [ ] All 8 active life entities still appear and project correctly
