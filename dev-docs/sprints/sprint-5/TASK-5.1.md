# TASK-5.1: Fix Status Change Comparison Math

**Status:** TODO
**Sprint:** 5
**Priority:** P0 (critical — visible calculation error)
**Est. effort:** 1 hr
**Dependencies:** None

## Context

The status change comparison table (Projets → Changement de statut juridique) displays incorrect values in the "Différence" column. With the current test data (CA 67,200€, AE vs SASU):

- **AE Net après cotisations:** 55,580€
- **SASU Net après cotisations:** 40,470€
- **Displayed difference:** 0€/an ← **WRONG** (should be -15,110€/an)
- **Cotisations sociales difference:** +0€ ← **WRONG** (AE: -11,620 vs SASU: -26,730 = -15,110€)

The yellow conclusion box ("L'AE reste plus avantageux…") reaches the correct conclusion, but the numbers in the difference column are broken. This is a trust-destroying bug — if the user sees one wrong number, they question every number in the tool.

## Root Cause Investigation

Check `frontend/src/routes/(app)/projects/+page.svelte` (or wherever the status change comparison renders). The diff calculation likely has one of these bugs:
1. Computing `AE - SASU` but displaying `abs()` or ignoring sign
2. Computing diff on the wrong fields (e.g., diffing base cotisations instead of the actual amounts)
3. A reactive update issue where diff computes before SASU values are ready
4. The comparison is done client-side with display values (formatted strings) instead of raw numbers

Also check: `backend/app/routers/projects.py` or `profile.py` — if the comparison is server-computed, the bug may be in the API response.

## Requirements

1. **Fix the difference calculation** for every row in the comparison table:
   - CA annuel brut: same → "–" (correct today)
   - Charges déductibles: AE 22,848 - SASU 7,800 = **-15,048€** (show with sign + color)
   - Base cotisations: AE 44,352 - SASU 59,400 = **+15,048€**
   - Cotisations sociales: AE -11,620 - SASU -26,730 = **+15,110€** (AE pays less)
   - Net après cotisations: AE 55,580 - SASU 40,470 = **+15,110€** (AE keeps more)

2. **Sign convention:** Positive (emerald) = AE is better by this amount. Negative (rose) = SASU is better. Zero = neutral ("–").

3. **Verify the conclusion logic** still works: "L'AE reste plus avantageux" when AE net > SASU net, "Le passage en {target} serait avantageux" when SASU net > AE net.

4. **Edge cases to test:**
   - Very high CA where SASU becomes advantageous (typically above ~80k CA with high real charges)
   - Zero real charges (AE should always win since forfaitaire > 0)
   - Charges exactly equal to abattement (breakeven point)

## Acceptance Criteria

- [ ] Difference column shows mathematically correct values for all rows
- [ ] Positive diffs (AE advantage) in emerald, negative (SASU advantage) in rose
- [ ] Conclusion text matches the actual numbers
- [ ] Tested with at least 3 CA levels: low (30k), medium (67k current), high (100k)
- [ ] No rounding errors visible (values should match to the euro)
- [ ] LEARNINGS.md updated
