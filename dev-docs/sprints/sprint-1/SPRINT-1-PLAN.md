# Sprint 1: Data Model & Identity

**Status:** BACKLOG
**Created:** 2026-05-07
**Predecessor:** Sprint 0 (Fork & Strip)
**Goal:** User financial profile, AE cotisation rate engine, expense model, and the first three frontend sections (Identité, Revenus, Charges) fully wired to the backend.

---

## Why this sprint exists

Sprint 0 left us with a clean shell. Sprint 1 builds the data foundation — the user profile that everything else hangs off. By the end of this sprint a user can log in, configure their financial identity (age, AE status, CA, growth expectations, expenses, tax breaks), and see their numbers reflected live. No projections yet (Sprint 4), no life entities (Sprint 2), but the core "who am I financially" is complete.

---

## Task Index

| ID | Task | Priority | Est. | Dep. |
|----|------|----------|------|------|
| **1.1** | UserProfile Model & API | P0 | 1.5 hr | 0.2 |
| **1.2** | AE Cotisation Rate Engine | P0 | 1 hr | None |
| **1.3** | Inflation Scales & Growth Presets | P1 | 30 min | None |
| **1.4** | Monthly Expense Schema | P0 | 1 hr | 1.1 |
| **1.5** | Identity Frontend Section | P0 | 2 hr | 1.1, 1.2, 0.4 |
| **1.6** | Revenue Frontend Section | P1 | 2 hr | 1.1, 1.2, 1.3 |
| **1.7** | Expenses Frontend Section | P1 | 1.5 hr | 1.4, 1.3 |
| **1.8** | Sidebar Quick Stats (live) | P2 | 1 hr | 1.1, 1.2, 1.4 |

## Execution Order

**1.2 → 1.3 → 1.1 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8**

Rationale:
- **1.2 and 1.3 first** — pure calculation modules with no DB dependency. Can be built and tested in isolation.
- **1.1 third** — the DB model that the frontend sections need.
- **1.4 fourth** — extends 1.1 with expense data.
- **1.5/1.6/1.7** — frontend sections in order of dependency. Identity first (simplest), Revenue second (needs growth presets), Expenses third (needs inflation scales).
- **1.8 last** — polish task wiring sidebar stats to real data.

## Definition of Sprint-Done

- UserProfile model created with Alembic migration
- `GET/PUT /api/profile` working with auth
- AE rate schedule returns time-dependent rates for all 4 activity types
- Growth presets and inflation scales served via API
- Identity section: saves age, target, parts, AE type, VL toggle; shows rate schedule preview
- Revenue section: saves CA, growth preset; shows 5-year preview, CESU/charity inputs with live credit calc
- Expenses section: saves 12 expense categories; shows inflation preview table across 3 scales
- Sidebar shows live CA/mois and total épargne from profile data
- All text via i18n keys
- All financial calculations in backend (frontend is display-only)
- Unit tests for rate engine, inflation scales, expense validation
- LEARNINGS.md updated

## Out of scope

- Life entities (Sprint 2)
- Investment tracking (Sprint 3)
- Projects / status change simulation (Sprint 3)
- Projection engine (Sprint 4)
- Charts (Sprint 4)
- AI features (Sprint 5)
- CAF auto-estimation logic (Sprint 2 — needs kid count)
