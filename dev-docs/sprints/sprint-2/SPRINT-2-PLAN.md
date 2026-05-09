# Sprint 2: Life Entities & Expense Lifecycles

**Status:** BACKLOG
**Created:** 2026-05-07
**Predecessor:** Sprint 1 (Data Model & Identity)
**Goal:** The progressive lifecycle engine. Kids, pets, cars, tech — each with age-aware cost events that start, evolve, and stop over time. Plus recurring bounded expenses and CAF auto-estimation.

---

## Why this sprint exists

This is the conceptual heart of Horizon 30. Most financial planners treat expenses as a flat monthly number. Horizon 30 models them as **lifecycle streams** — a 1-year-old generates crèche costs now, but in 2 years she enters maternelle (cantine replaces crèche), at 6 summer camps start, at 18 university and first car, at ~23 the costs stop. A dog costs more at ages < 2 and > 10. A car needs CT every 2 years after age 4 and gets replaced every 8 years. This sprint builds the data model, the canned defaults engine (including the French September school entry rule), and the full "Vie" frontend section.

By the end of this sprint the user has a complete picture of their life's cost structure over time — not just "what I pay today" but "what I'll pay in 2035 when my eldest is in university and my youngest is in collège and my car is due for replacement."

---

## Key Concept: Progressive Calculation

When a user adds a child born 2025-03-15:
1. System computes: born in March → enters maternelle September 2028 (age 3)
2. Pre-populates cost events with age brackets:
   - Crèche (0→3): 500€/month
   - Cantine + périscolaire (3→11): 150€/month
   - Camp d'été (6→17): 800€/year
   - Activités extra (6→18): 100€/month
   - Lycée fournitures (15→18): 600€/year
   - Permis + 1ère voiture (18→18): 5 000€ one-time
   - Études supérieures (18→23): 500€/month
3. Each event is labeled `source: "default"` — user can edit amounts, add custom events, or remove canned ones
4. The projection engine (Sprint 4) walks each entity's events per year and includes only active ones

This same pattern applies to pets (vet costs increase with age), cars (CT every 2 years, replacement at cycle end), and tech (periodic replacement with inflation).

---

## Task Index

| ID | Task | Priority | Est. | Dep. |
|----|------|----------|------|------|
| **2.1** | LifeEntity Model & CRUD API | P0 | 1.5 hr | 1.1 |
| **2.2** | Canned Defaults Service | P0 | 2 hr | 2.1 |
| **2.3** | RecurringExpense Model & API | P1 | 1 hr | 1.1 |
| **2.4** | CAF Auto-Estimation Service | P1 | 1 hr | 2.1 |
| **2.5** | Life Page — Kids Section | P0 | 2.5 hr | 2.1, 2.2 |
| **2.6** | Life Page — Pets Section | P1 | 1.5 hr | 2.5 |
| **2.7** | Life Page — Cars & Tech Sections | P1 | 2 hr | 2.5 |
| **2.8** | Life Page — Recurring Expenses + Assembly | P1 | 1.5 hr | 2.3, 2.5 |

## Execution Order

**2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → 2.8**

Rationale: Backend models first (2.1-2.4), then frontend in order of complexity. Kids first (2.5) because it creates the reusable components. Pets (2.6) and Cars/Tech (2.7) reuse those components. Recurring + assembly (2.8) ties it all together.

## Definition of Sprint-Done

- LifeEntity table created, CRUD works for all 4 types (kid, pet, car, tech)
- Adding a kid auto-populates age-appropriate cost events with September rule
- Adding a pet/car/tech auto-populates type-specific cost events
- Cost events show active/future/past visual states based on entity's current age
- User can edit amounts, add custom events, remove canned events
- RecurringExpense table created, CRUD works
- CAF auto-estimation returns reasonable monthly amount based on kid count + income
- Full "Vie" page renders all 5 sections (kids, pets, cars, tech, recurring)
- Sidebar kid count updates when kids are added/removed
- All text via i18n keys, all calculations in backend
- Unit tests for: canned defaults (September rule), CAF estimation, cost event validation
- LEARNINGS.md updated

## Out of scope

- Investment tracking (Sprint 3)
- Project P&Ls (Sprint 3)
- Projection engine using life entity data (Sprint 4)
- AI lifecycle suggestions (Sprint 5)
- Regional cost variations (future — MVP uses national averages)
