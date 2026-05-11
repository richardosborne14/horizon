# Sprint 7: Couple Mode, Revenue Overhaul, Tax Intelligence & Advisory Engine

**Status:** BACKLOG
**Created:** 2026-05-10
**Predecessor:** Sprint 6 (Deep Intelligence)
**Goal:** Transform Horizon from a single-person simulator into a household advisor. Add couple mode, rich income source modeling, simplified IR tax, goal-backward solving, drawdown strategy, and a monthly action plan. By the end, the app doesn't just project — it *advises*.

---

## Why this sprint exists

Sprints 1–6 built a 30-year projection engine. Sprint 7 closes the gap between "here's your trajectory" and "here's what to do about it." Four pillars:

1. **Couple mode** — Spouse with career history, pension, conjointe collaboratrice. Two earners, two pension streams, shared expenses.

2. **Revenue overhaul** — Replace the single CA field with tracked income sources (clients, products, dividends, asset sales) each with duration, growth, and confidence. Future income events in Projets.

3. **Tax & drawdown intelligence** — Simplified IR model with quotient familial (the biggest missing accuracy piece), retirement drawdown ordering (PEA→AV→PER tax optimization), real estate appreciation.

4. **Advisory engine** — Goal-backward solver ("what would it take to retire at 58?"), prescriptive life-phase advice, confidence bands on charts, and a monthly action plan dashboard.

---

## Task Index

| ID | Task | Priority | Est. | Dep. |
|----|------|----------|------|------|
| **7.1** | Bug Fix: Sensitivity Analysis Zeros | P0 | 1 hr | — |
| **7.2** | Bug Fix: BRUT/NET Labels | P0 | 30 min | — |
| **7.3** | Custom Expense Categories | P0 | 2 hr | — |
| **7.4** | Spouse/Partner Data Model & API | P1 | 3 hr | — |
| **7.5** | Income Source Model & API | P1 | 3 hr | — |
| **7.6** | Revenue Page Overhaul — Frontend | P1 | 3 hr | 7.5 |
| **7.7** | Spouse Career History & Pension | P1 | 2.5 hr | 7.4, 6.1 |
| **7.8** | Couple-Aware Projection Engine | P2 | 3 hr | 7.4, 7.5, 7.7 |
| **7.9** | Couple Frontend — Identity & Revenue | P2 | 2.5 hr | 7.4, 7.6, 7.7 |
| **7.10** | Income Events in Projets | P2 | 2 hr | 7.5 |
| **7.11** | Goal-Backward Solver | P1 | 3 hr | 4.1 |
| **7.12** | Simplified IR Tax Model | P1 | 3 hr | — |
| **7.13** | Retirement Drawdown Strategy | P2 | 2.5 hr | 4.1 |
| **7.14** | Confidence Bands on Charts | P2 | 1.5 hr | 7.5 |
| **7.15** | Prescriptive Life-Phase Intelligence | P2 | 2 hr | 6.6, 6.9 |
| **7.16** | Real Estate Appreciation Model | P2 | 2 hr | 6.5 |
| **7.17** | Monthly Action Plan Dashboard | P2 | 3 hr | 7.11, 7.13 |

## Execution Order

**Phase 1 — Quick fixes (independent, ship immediately):**
7.1 → 7.2 → 7.3

**Phase 2 — Backend foundations (models + engines, no frontend):**
7.5 → 7.4 → 7.12 → 7.11

**Phase 3 — Revenue + couple frontend:**
7.6 → 7.7 → 7.10 → 7.9

**Phase 4 — Engine integration:**
7.8 → 7.13

**Phase 5 — Advisory layer + polish:**
7.14 → 7.15 → 7.16 → 7.17

Phases can overlap. Phase 1 is independent. Phase 2 tasks are backend-only. Phase 3 can start once 7.5 is done. Phase 4 needs most of 2 and 3. Phase 5 is additive polish.

---

## Definition of Sprint-Done

### Fixes & Polish
- Sensitivity analysis shows non-zero bars with meaningful narrative
- BRUT/NET labels clear on career history and revenue inputs
- Custom expense categories add/remove/save on Charges page

### Couple Mode
- Spouse model with CC logic, CRUD, career history, pension
- Projection engine handles household income and dual pension
- Spouse UI on Identity, Revenue, Runway pages

### Revenue Overhaul
- Income source model replaces single CA field
- Revenue page shows sources by earner with timeline preview
- Future income events in Projets (sales, dividends, new contracts)

### Tax & Drawdown
- Simplified IR with quotient familial and tranches
- Retirement drawdown ordering (PEA→AV→PER) with tax optimization
- Real estate appreciation feeds net worth and downsizing scenarios

### Advisory Engine
- Goal-backward solver answers "what would it take to reach X by age Y?"
- Confidence bands on wealth/income charts
- Life-phase prescriptive advice ("redirect freed mortgage to PEA")
- Monthly action plan dashboard with prioritized next steps

### Quality
- All calculations unit tested
- Hand-verified for 2 couple scenarios and 2 goal-backward scenarios
- All text via i18n keys
- LEARNINGS.md updated

## Out of scope

- Full IR simulation with all edge cases (simplified model only)
- Monte Carlo / probabilistic projections
- Divorce/separation financial modeling
- Child custody cost sharing
- Spouse's own separate investment accounts
- Multiple spouses/partners
- AI-generated advice (advisory is rule-based, not LLM)
