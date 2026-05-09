# Sprint 4: Projection Engine & Runway

**Status:** BACKLOG
**Created:** 2026-05-07
**Predecessor:** Sprint 3 (Savings & Projects)
**Goal:** The 30-year calculation engine and the Horizon dashboard — the view the user actually lives in. Wealth trajectory, income charts, milestones, goal tracking, detailed table, contextual insights.

---

## Why this sprint exists

Sprints 1-3 built the configuration. Sprint 4 is the payoff — the engine that ingests everything (profile, expenses, life entities, savings, projects, status change) and produces a year-by-year projection from age 40 to age 70. This is the entire point of the app: "if I do X, Y, and Z consistently for 30 years, here's what happens."

The projection engine is the most complex single piece of code in Horizon 30. It walks every year, queries every data source, compounds every investment, ages every kid, replaces every car, and produces a timeline the frontend renders as charts, milestones, and a detailed table. Getting this right — especially the compounding math and lifecycle event timing — is critical.

---

## Task Index

| ID | Task | Priority | Est. | Dep. |
|----|------|----------|------|------|
| **4.1** | Projection Engine — Core Calculation | P0 | Half day | 1.2, 1.3, 1.4, 2.1, 2.3, 2.4, 3.1, 3.2 |
| **4.2** | Projection API Endpoint | P0 | 1 hr | 4.1 |
| **4.3** | Runway — Scale Selector, Goal & Hero Stats | P0 | 1.5 hr | 4.2 |
| **4.4** | Runway — Wealth & Income Charts | P0 | 2 hr | 4.2 |
| **4.5** | Runway — Milestones & Projection Table | P1 | 1.5 hr | 4.2 |
| **4.6** | Runway — Insights & Page Assembly | P1 | 1.5 hr | 4.3, 4.4, 4.5 |
| **4.7** | Cross-Section Navigation Polish | P2 | 1 hr | 4.6 |

## Execution Order

**4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6 → 4.7**

Strictly sequential. The engine must work before the API, the API before the frontend, and the frontend components before assembly.

## Definition of Sprint-Done

- Projection engine computes 30-year timeline from all data sources
- API returns timeline in < 500ms with all intermediate values
- Runway page renders: scale selector, goal input, hero stats, 2 charts, milestones, table, insights
- Scale toggle (optimistic/moderate/pessimistic) recomputes projection live
- Goal line renders on income chart, "achieved in year X" message shown
- Wealth milestones (100k, 250k, 500k, 1M) appear at correct years
- Table shows every 5th year + final year with color-coded columns
- Insight cards react to projection outcome (goal reached / gap to close)
- Hand-verified math against at least 3 test scenarios
- Unit tests for engine covering: bare minimum profile, moderate saver, aggressive investor
- LEARNINGS.md updated

## Out of scope

- AI analysis of the projection (Sprint 5)
- PDF export of the projection
- Sharing/comparing projections
- Monte Carlo simulation (future — deterministic projections only for MVP)
