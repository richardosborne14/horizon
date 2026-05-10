# Sprint 6: Deep Intelligence — Career History, Financial Lifecycles & Sensitivity

**Status:** IN PROGRESS (Backend complete, Frontend in progress)
**Created:** 2026-05-09
**Predecessor:** Sprint 5 (Calculation Depth & Insights)
**Goal:** Transform Horizon from "what do I earn and spend today projected forward" into "the system knows my entire financial life — past, present, and future — and reasons about it."

---

## Why this sprint exists

Sprint 5 made the projection engine honest (post-retirement modeling, insights, readiness score). Sprint 6 makes it *intelligent*. The difference between a good simulator and an indispensable planning tool is context: knowing that a CDI from 2012–2020 means 32 validated trimestres at a higher salary base than AE, that the mortgage ends in 2035 freeing up 590€/month, that both cars are past their lifecycle and need replacement *now*, and that all of these facts interact.

Three pillars:

1. **Career history** — Past employment feeds pension calculation and gives the engine a complete income picture. An 8-year CDI at full-time salary generates significantly more pension rights than AE income. Without this, the pension estimate (Task 5.3) is based on AE trimestres alone, which systematically underestimates retirement income.

2. **Financial lifecycles** — Loans, mortgages, and major expenses have end dates. The current model treats "credit: 590€/mois" as permanent. That's wildly wrong for a mortgage that ends in 2035. This sprint adds proper temporal modeling to every expense category that has a natural termination point, and fixes the car lifecycle bug where both vehicles contribute zero.

3. **Sensitivity & net worth** — The user needs to know which decisions actually matter. Is it the savings rate? The growth rate? The investment allocation? A sensitivity analysis ranks the levers by impact. And a proper net worth snapshot (cash, debts, property value) gives the engine an honest starting point.

---

## Task Index

| ID | Task | Priority | Est. | Dep. |
|----|------|----------|------|------|
| **6.1** | Career History Model & API | P0 | 2.5 hr | — |
| **6.2** | Pension Engine v2 (Career-Aware) | P0 | 3 hr | 6.1, 5.3 |
| **6.3** | Loan & Mortgage Lifecycle | P0 | 2.5 hr | — |
| **6.4** | Car Lifecycle Overhaul | P0 | 2 hr | — |
| **6.5** | Net Worth Snapshot | P1 | 2 hr | — |
| **6.6** | Expense Evolution Timeline | P1 | 2 hr | 6.3 |
| **6.7** | Sensitivity Analysis Engine | P1 | 3 hr | 5.4 |
| **6.8** | Disposable Income Waterfall | P1 | 2 hr | — |
| **6.9** | Smart Lifecycle Alerts | P2 | 2 hr | 6.3, 6.4, 5.4 |
| **6.10** | Projection Explainer — Year Drill-Down | P2 | 2 hr | 5.6 |

## Execution Order

**6.4 → 6.3 → 6.1 → 6.2 → 6.5 → 6.6 → 6.7 → 6.8 → 6.9 → 6.10**

Fix the car bug first (quick, high-impact). Then loans/mortgages (transforms expense accuracy). Then career history → pension (the big intelligence gain). Then net worth, expense evolution, sensitivity, and polish.

## Definition of Sprint-Done

- Career history stores past employment with dates, salary, employer type
- Pension estimation uses CDI trimestres + AE trimestres for accurate calculation
- Loans/mortgages modeled with end dates; expenses drop when loans terminate
- Car lifecycle handles expired entities, rolling replacement, and replacement prompts
- Net worth snapshot includes cash reserves, debts, and property value
- Expense evolution shows how costs change over time (mortgage ends, kids leave, etc.)
- Sensitivity analysis ranks the top 5 parameters by impact on final wealth
- Disposable income waterfall shows where money flows from gross to savings
- Smart alerts fire for lifecycle events ("mortgage ends in 2035, redirect 590€/mois")
- Year drill-down lets the user click any projection year and see the full breakdown
- All calculations hand-verified, unit tested, LEARNINGS.md updated

## Out of scope

- Full income tax (IR) simulation (complex; defer to Sprint 7)
- Monte Carlo / probabilistic projections (future)
- Multiple income sources (freelance + part-time CDI simultaneously)
- Property valuation appreciation model (net worth records value, doesn't project it)
- Couple/household joint projection
