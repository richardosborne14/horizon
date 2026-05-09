# Sprint 0: Fork & Strip

**Status:** DONE ✅ (2026-05-08)
**Created:** 2026-05-07
**Goal:** Fork ComCoi, remove salon domain, keep infrastructure. Clean slate for Horizon 30.

---

## Why this sprint exists

Horizon 30 reuses ComCoi's proven infrastructure — SvelteKit, FastAPI, PostgreSQL, Docker, auth, i18n, Stripe webhooks — but replaces the entire domain layer. Rather than build from scratch, we strip what we don't need and keep what we do. This sprint ends with a running app that has: auth, a dark-themed sidebar nav with 7 placeholder sections, a clean DB, and zero salon references.

---

## Task Index

| ID | Task | Priority | Est. | Dep. |
|----|------|----------|------|------|
| **0.1** | Fork Repository & Rename | P0 | 30 min | None |
| **0.2** | Strip Salon Domain — Backend | P0 | 2 hr | 0.1 |
| **0.3** | Strip Salon Domain — Frontend | P0 | 2 hr | 0.1 |
| **0.4** | Dark Theme Design Tokens | P1 | 1 hr | 0.3 |
| **0.5** | i18n Reset | P1 | 30 min | 0.3 |
| **0.6** | Prototype Reference Doc | P2 | 30 min | None |

## Execution Order

**0.1 → 0.6 → 0.2 → 0.3 → 0.4 → 0.5**

Rationale:
- **0.1 first** — everything depends on the fork existing.
- **0.6 second** — commit the prototype reference before any UI work so Cline has the style guide.
- **0.2 third** — strip backend first so frontend work doesn't hit missing imports.
- **0.3 fourth** — strip frontend routes, add sidebar nav layout.
- **0.4 fifth** — apply dark theme once the layout shell exists.
- **0.5 last** — reset i18n keys once we know what sections are called.

## Definition of Sprint-Done

- `docker compose up -d` builds and runs without errors
- Login → lands on app shell with dark sidebar nav showing 7 sections
- Each section shows a placeholder page with section title
- No references to "Communauté Coiffure", "Atlas", "CoCo", or salon-specific terms in user-facing strings
- DB has only: users, admin_config, stripe_events_processed tables
- Prototype JSX committed to dev-docs/prototype/
- LEARNINGS.md updated with any fork-specific gotchas

## Out of scope

- No new models (Sprint 1)
- No financial calculations (Sprint 1+)
- No data entry forms (Sprint 1+)
- No AI features (Sprint 5)
