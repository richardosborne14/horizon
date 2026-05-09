# Sprint 3: Savings & Projects

**Status:** BACKLOG
**Created:** 2026-05-07
**Predecessor:** Sprint 2 (Life Entities)
**Goal:** Investment vehicle tracking with allocation strategy, project mini-P&Ls (gîte, rental property), life events (wedding, big trip), and status change simulation (AE → EIRL). The "Épargne" and "Projets" sections fully wired.

---

## Why this sprint exists

Sprints 1-2 built the "cost" side: what you earn, what you spend, what your life costs over time. Sprint 3 builds the "accumulation" side: where your money goes to grow, what investment projects generate income, and what structural changes (like switching from AE to EIRL) could increase your disposable income. By the end of this sprint the user has configured everything the projection engine (Sprint 4) needs to compute a 30-year runway.

---

## Task Index

| ID | Task | Priority | Est. | Dep. |
|----|------|----------|------|------|
| **3.1** | Investment Vehicles & Allocation Model | P0 | 1.5 hr | 1.1 |
| **3.2** | Project Model & P&L Computation | P0 | 2 hr | 1.1 |
| **3.3** | Savings Frontend Section | P0 | 2 hr | 3.1 |
| **3.4** | Projects Frontend — Investments | P1 | 2 hr | 3.2 |
| **3.5** | Projects Frontend — Life Events | P1 | 1 hr | 3.2 |
| **3.6** | Projects Frontend — Status Change + Assembly | P1 | 1.5 hr | 3.4, 3.5 |

## Execution Order

**3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6**

Backend models first (3.1, 3.2), then frontend in order. Savings before Projects because it's simpler and validates the pattern.

## Definition of Sprint-Done

- InvestmentAllocation model created, 7 vehicle types with specs served via API
- User can set existing balances and monthly contributions per vehicle
- Project model supports both investment and life-event types
- Investment projects show live mini-P&L (net income, tax, yield %)
- Life events stored with year and cost
- Status change simulation UI wired to profile fields (already on the model from TASK-1.1)
- Sidebar "Épargne/m" and "Projets" counts update live
- All text via i18n keys
- Unit tests for: vehicle specs, P&L computation, allocation validation
- LEARNINGS.md updated

## Out of scope

- Projection engine consuming this data (Sprint 4)
- Charts (Sprint 4)
- AI scenario analysis (Sprint 5)
- Actual Stripe payments for premium features (future)
- Portfolio rebalancing suggestions (future)
