# Sprint 7 — Session Plan

**Created:** 2026-05-10
**Goal:** Break 17 tasks into 8 sensible sessions to avoid context overstretching.

---

## Session 1: Quick Fixes (~3.5 hrs)
**Tasks:** 7.1 → 7.2 → 7.3
**Rationale:** All independent. User-visible improvements. Ship immediately.

| Task | Description | Effort | Deps |
|------|-------------|--------|------|
| 7.1 | Bug Fix — Sensitivity Analysis Zeros | 1 hr | — |
| 7.2 | Bug Fix — BRUT/NET Labels | 30 min | — |
| 7.3 | Custom Expense Categories | 2 hr | — |

---

## Session 2: Backend Foundations — Income & Spouse (~6 hrs)
**Tasks:** 7.5 → 7.4
**Rationale:** Two foundational data models. Both backend-only. Unblocks everything downstream.

| Task | Description | Effort | Deps |
|------|-------------|--------|------|
| 7.5 | Income Source Model & API | 3 hr | — |
| 7.4 | Spouse/Partner Data Model & API | 3 hr | — |

---

## Session 3: Backend Intelligence — Tax & Goals (~6 hrs)
**Tasks:** 7.12 → 7.11
**Rationale:** Standalone backend calculations. Big user impact.

| Task | Description | Effort | Deps |
|------|-------------|--------|------|
| 7.12 | Simplified IR Tax Model | 3 hr | — |
| 7.11 | Goal-Backward Solver | 3 hr | 4.1 |

---

## Session 4: Revenue Frontend Overhaul (~5 hrs)
**Tasks:** 7.6 → 7.10
**Rationale:** Both consume income_sources API from 7.5. Cohesive frontend session.

| Task | Description | Effort | Deps |
|------|-------------|--------|------|
| 7.6 | Revenue Page Overhaul — Frontend | 3 hr | 7.5 |
| 7.10 | Income Events in Projets | 2 hr | 7.5 |

---

## Session 5: Spouse Frontend (~5.5 hrs)
**Tasks:** 7.7 → 7.9
**Rationale:** Spouse career + UI. Must be after Session 4 (7.9 depends on 7.6).

| Task | Description | Effort | Deps |
|------|-------------|--------|------|
| 7.7 | Spouse Career History & Pension | 2.5 hr | 7.4, 6.1 |
| 7.9 | Couple Frontend — Identity & Revenue | 2.5 hr | 7.4, 7.6, 7.7 |

---

## Session 6: Engine Integration (~5.5 hrs)
**Tasks:** 7.8 → 7.13
**Rationale:** Both modify projection.py. 7.8 integrates all couple/income work. 7.13 replaces 4% rule.

| Task | Description | Effort | Deps |
|------|-------------|--------|------|
| 7.8 | Couple-Aware Projection Engine | 3 hr | 7.4, 7.5, 7.7 |
| 7.13 | Retirement Drawdown Strategy | 2.5 hr | 4.1 |

---

## Session 7: Advisory Layer (~5.5 hrs)
**Tasks:** 7.14 → 7.15 → 7.16
**Rationale:** "Advisor" features. Add polish and guidance. Relatively independent of each other.

| Task | Description | Effort | Deps |
|------|-------------|--------|------|
| 7.14 | Confidence Bands on Charts | 1.5 hr | 7.5 |
| 7.15 | Prescriptive Life-Phase Intelligence | 2 hr | 6.6, 6.9 |
| 7.16 | Real Estate Appreciation Model | 2 hr | 6.5 |

---

## Session 8: Monthly Action Plan (~3 hrs)
**Tasks:** 7.17
**Rationale:** Caps the sprint. Depends on goal solver + drawdown.

| Task | Description | Effort | Deps |
|------|-------------|--------|------|
| 7.17 | Monthly Action Plan Dashboard | 3 hr | 7.11, 7.13 |

---

## Key Risks

1. **7.8 (Couple Engine)**: Highest risk — touches core projection loop. Backward-compat fallback is well-designed.
2. **7.12 (IR Tax)**: Will shift all existing projection test assertions since `net_annual` now includes IR.
3. **7.11 (Goal Solver)**: ~100 projection passes per request. Target < 3s.
4. **Alembic migrations**: Hand-write required (LEARNINGS #12 — autogenerate produces phantom ComCoi table drops).
5. **Frontend rebuild**: After every session with frontend changes: `docker compose build frontend && docker compose up -d frontend`.

---

## Progress

| Session | Tasks | Status | Completed |
|---------|-------|--------|-----------|
| 1 | 7.1, 7.2, 7.3 | 🟢 | 2026-05-10 — All 3 tasks already implemented. Verified API returns valid data, labels correct, custom expenses functional. |
| 2 | 7.5, 7.4 | 🟢 | 2026-05-10 — Verified: 19/19 tests pass, migrations 055/056 applied. income_sources + spouse APIs fully functional. |
| 3 | 7.12, 7.11 | 🟢 | 2026-05-10 — Implemented: IR tax model (27/27 tests), engine integration, goal-backward solver (16/16 tests). 92/92 total tests pass. |
| 4 | 7.6, 7.10 | 🟢 | 2026-05-10 — Revenue page overhaul complete: income sources list, quick-add presets, 10-year timeline, stats from sources. Projects page: income events section. i18n keys added. |
| 5 | 7.7, 7.9 | 🟢 | 2026-05-10 — Verified: all code present. Backend: owner column, career filter, CC trimestres, combined pension endpoint. Frontend: spouse card, CC options, tax parts prompt, spouse career timeline, runway/sidebar household stats. |
| 6 | 7.8, 7.13 | 🟢 | 2026-05-11 — Implemented: ProjectionInput extended with spouse (monthly_gross, ae_type, pension, growth_rate, retirement_age), CC annual cotisation, income_sources list. compute_income_for_year / compute_onetime_income helpers. _compute_accumulation_year integrates spouse income + cotisations + CC expense + income sources. _compute_retirement_year uses household pension (user + spouse). drawdown.py module created (PEA→AV→SCPI→PER tax-optimized withdrawal, 6-month liquidity buffer, AV abattement single/couple). Spouse sensitivity nudge added (skipped when no spouse). _assemble_input in router loads spouse projection fields + income sources. All 88 tests pass (49 projection + 8 drawdown + 17 sensitivity + 14 spouse_career). |
| 7 | 7.14, 7.15, 7.16 | 🟢 | 2026-05-11 — 7.16: property model/migration/schema/router/tests (10/10 pass). 7.15: advice.py module + tests (12/12 pass). 7.14: confidence bands frontend (multi-projection fetch, SVG bands, low-confidence widening). |
| 8 | 7.17 | 🟢 | 2026-05-11 — action_plan.py module + tests (12/12 pass), API endpoint, frontend rendering on Runway page. All 46 new tests pass (34 sprint-7 + 12 existing property). |
