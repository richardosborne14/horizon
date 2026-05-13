# Hotfix Batch — May 2026 Audit

**Generated:** 2026-05-12  
**Source:** Live DB + UI audit against richard@digitalbricks.io  
**Execute with:** DeepSeek V4 PRO, one file at a time in the order below

---

## Execution Order (dependencies matter)

```
HOTFIX-1  ←  Run first. Critical backend fix. No dependencies.
    ↓
HOTFIX-2  ←  Run second. Frontend display fix. No dependencies on HOTFIX-1
             but deploy together so the waterfall is complete.
    ↓
HOTFIX-3  ←  Run third. Requires HOTFIX-2 deployed (waterfall must show
             conjoint income before we apply charges to it).
    ↓
HOTFIX-4  ←  Run fourth. Requires HOTFIX-3 (spouse record must be correct
             before pension logic runs).
    ↓
HOTFIX-5  ←  Independent. Can run any time after HOTFIX-1.
HOTFIX-6  ←  Independent. Can run any time. Pure DB cleanup + minor UI.
HOTFIX-7  ←  Requires HOTFIX-1 deployed first (chart must reflect grown values).
```

---

## Summary Table

| File | Issue | Severity | Files Changed | Risk |
|------|-------|----------|---------------|------|
| HOTFIX-1 | Income growth not applied in projection | 🔴 CRITICAL | 1–2 backend | Low — pure additive |
| HOTFIX-2 | Waterfall excludes conjoint salary | 🔴 HIGH | 1 backend + 1 frontend | Low — additive row |
| HOTFIX-3 | Conjoint earner wrong, no spouse charges | 🟠 HIGH | 1 SQL + 1 backend | Medium — changes NET |
| HOTFIX-4 | Caro pension invisible, no alert | 🟡 MEDIUM | 2–3 files | Low — additive |
| HOTFIX-5 | MacBook 2024 missing annual events | 🟡 MEDIUM | 1 SQL + 1 backend | Low |
| HOTFIX-6 | Inactive entity cruft + test expense | 🟢 LOW | 1 SQL + 1 frontend | Low — DB cleanup only |
| HOTFIX-7 | Revenue timeline chart shows flat growth | 🟡 MEDIUM | 1–2 files | Low — chart only |

---

## Expected outcome after all 7 hotfixes

**Before hotfixes (what the app showed):**
- Monthly net: −194€ (false deficit in waterfall)
- Projection: income flat at 79,200€ while expenses inflate to 100,000+ by 2051
- Patrimoine épuisé à 76 ans (false alarm)
- Caro's pension: invisible (0€)
- Caro's charges: not deducted

**After hotfixes (correct picture):**
- Monthly net: ~+540€ surplus (after spouse charges properly deducted)
- Projection: income grows 6%/year from 79,200€ → ~455,000€ by retirement
- Patrimoine at 70: substantially larger; exhaustion warning removed or deferred well beyond 95
- Caro's pension: visible once her career history is entered
- Spouse charges: ~2,760€/year correctly deducted

---

## Notes for DeepSeek

- Run files strictly in order. Do not combine tasks.
- Each file contains a `SCOPE BOUNDARY` section with explicit `DO NOT` lists. Follow them.
- Each file ends with a `DONE WHEN` checklist. Stop when all boxes are checked.
- HOTFIX-3 includes a SQL UPDATE. Run the SELECT verification query first and confirm 1 row before executing.
- HOTFIX-6 includes DELETEs. Run the SELECT queries first and confirm expected row counts before executing any DELETE.
