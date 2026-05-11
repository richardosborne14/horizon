# TASK-7.1: Bug Fix — Sensitivity Analysis Zeros

**Status:** DONE — Bug already resolved. Backend API returns valid non-zero delta_wealth for 5/6 parameters. All 16 sensitivity tests pass. Frontend fetches through proxy correctly.
**Sprint:** 7
**Priority:** P0 (critical — visible bug on the main dashboard)
**Est. effort:** 1 hr
**Dependencies:** None

---

## Context

The "Qu'est-ce qui compte le plus ?" section on the Horizon/Runway page shows all sensitivity parameters at 0€. The sensitivity engine (`backend/app/calculations/sensitivity.py`) runs 7 projection passes comparing nudged inputs against the baseline. The bars render at zero width and the amounts show 0€.

---

## Step-by-Step Instructions

### Step 1: Diagnose — Is the bug in the backend or frontend?

1. Start the dev stack: `docker compose up -d`
2. Log in as test user, ensure profile has: birth_date set, monthly_gross_ca > 0, at least one savings allocation > 0
3. Open browser devtools → Network tab
4. Navigate to the Runway page
5. Find the request to `GET /api/projection/sensitivity?scale=moderate`
6. Inspect the JSON response body — look at `parameters[0].delta_wealth`

**If `delta_wealth` values are "0" or "0.00" in the API response → the bug is in the backend.** Proceed to Step 2A.

**If `delta_wealth` values are non-zero in the API response but display as 0 on screen → the bug is in the frontend.** Proceed to Step 2B.

### Step 2A: Backend Fix

The most likely causes:

**Cause A1: `_total_monthly_savings()` returns 0 because no investments are allocated.**
- Check `backend/app/calculations/sensitivity.py` → the `monthly_savings` nudge adds 200 to `_total_monthly_savings()`
- If the user has zero savings allocations, the baseline and nudged projections both produce zero investment growth → delta is zero
- Fix: ensure the nudge works even when baseline is zero. The nudge should ADD 200€/mois to a default vehicle (e.g. Livret A) even if no allocations exist.

**Cause A2: `ProjectionInput` clone is not deep enough.**
- Check `copy.deepcopy(inp)` in `_apply_nudge()` — if investment allocations are a dict reference that isn't deep-copied, mutations might affect the baseline
- Fix: ensure `copy.deepcopy` is used, not `copy.copy`

**Cause A3: The sensitivity engine catches an exception silently and returns zero.**
- Check for bare `except` or `except Exception` blocks that swallow errors
- Fix: let exceptions propagate or log them

**Cause A4: Input assembly in the router is missing data.**
- Check `_assemble_input()` in `backend/app/routers/projection.py` — does it load investments, projects, life entities?
- If the input has no investments loaded, all investment-related nudges produce zero delta

After identifying and fixing: run `GET /api/projection/sensitivity?scale=moderate` again. Verify at least 4 of 7 parameters have non-zero `delta_wealth`.

### Step 2B: Frontend Fix

Check `frontend/src/routes/(app)/runway/+page.svelte`:

**Cause B1: Field name mismatch.**
- The template reads `param.delta_wealth` — verify this matches the API response field name exactly (check for `deltaWealth` vs `delta_wealth` — Python API returns snake_case, the frontend might expect camelCase if there's a transform layer)

**Cause B2: `sensitivityData` is not populated.**
- Check the `+page.server.ts` or the client-side fetch — is the sensitivity endpoint actually being called?
- If it's behind a conditional (e.g. only fetched when projection succeeds), check that the condition is met

**Cause B3: `parseFloat` on a string that isn't a number.**
- The bar width is: `Math.abs(parseFloat(param.delta_pct || '0')) * 2`
- If `delta_pct` is a string like "40.6" this works. If it's something unexpected, it returns NaN → 0

After fixing: verify the bars have visible widths and the amounts are non-zero.

### Step 3: Verify

1. Navigate to Runway page
2. "Qu'est-ce qui compte le plus ?" section should show 5-7 parameters with non-zero bars
3. Teal bars for positive deltas, rose for negative
4. The narrative text should mention the top lever specifically (not a generic placeholder)
5. Run existing projection tests: `cd backend && python -m pytest tests/test_projection.py -v`

---

## SCOPE BOUNDARY

- DO NOT refactor the sensitivity engine. Fix the bug only.
- DO NOT add new sensitivity parameters. That happens in TASK-7.8.
- DO NOT change the frontend layout of the sensitivity section.
- DO NOT add caching or performance optimization.
- Expected code change: 5-30 lines.

## DONE WHEN

- [ ] `GET /api/projection/sensitivity` returns non-zero `delta_wealth` for ≥4 parameters
- [ ] Frontend bars render with visible widths
- [ ] Amounts display non-zero values (e.g. "+72 000€", "+127k€")
- [ ] Narrative text references the top lever by name
- [ ] Existing tests pass
