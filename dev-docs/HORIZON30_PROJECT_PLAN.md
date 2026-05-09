# Horizon 30 — Project Plan & Task Documentation

## What This Is

A multi-decade wealth planning engine for French freelancers, forked from the Communauté Coiffure (ComCoi) codebase. Keeps the infrastructure (SvelteKit, FastAPI, PostgreSQL, Docker, auth, i18n, design tokens) and replaces the salon-specific domain with a personal finance lifecycle engine.

**Prototype / Style Guide:** The interactive React prototype built during brainstorming is the UX reference. See `/dev-docs/prototype/horizon30.jsx`. All section layouts, card styles, input patterns, dark theme tokens, and sidebar nav structure come from this prototype.

**Core Concept — Life Entity Lifecycle Engine:** Everything in Horizon 30 is a "life entity" with a cost lifecycle. Kids age out of crèche and into school. Cars get replaced every N years. iPhones cost more each generation. The engine models these as time-bounded cost streams that the projection engine aggregates into a 30-year runway. The system uses a combination of canned defaults (average crèche cost by region, average CT cost) and user overrides, with optional LLM intervention to suggest lifecycle events the user hasn't thought of.

---

## Stack (inherited from ComCoi)

| Layer | Tech | Notes |
|-------|------|-------|
| Frontend | SvelteKit | Dark theme, sidebar nav, design-tokens.css |
| Backend | FastAPI (Python) | Pydantic schemas, SQLAlchemy models |
| Database | PostgreSQL | Alembic migrations, NUMERIC(12,2) for money |
| AI | Anthropic Claude Sonnet | Lifecycle suggestions, scenario analysis |
| Hosting | Hetzner Cloud (DE) | Docker Compose |
| Payments | Stripe (future) | Freemium model TBD |

---

## .clinerules (Horizon 30)

```
# Project: Horizon 30 — Phase: MVP

## Dev Environment

| Resource | Value |
|----------|-------|
| **Local ports** | DB: 47432 · Backend: 47002 · Frontend: 47178 |
| **Start stack** | `docker compose up -d` from project root |
| **Frontend rebuild (source)** | `docker compose build frontend && docker compose up -d frontend` |
| **Frontend rebuild (packages)** | `docker compose build frontend && docker compose up -d -V frontend` |

## Before EVERY Task — Read These

1. `dev-docs/ARCHITECTURE.md` — system design, DB schema, projection engine
2. `dev-docs/LEARNINGS.md` — active gotchas
3. `dev-docs/PROTOTYPE_REFERENCE.md` — UX patterns from the prototype
4. Current sprint plan in `dev-docs/sprints/`

## Core Rules

### Quality
- Unit tests mandatory for all calculations, API endpoints, lifecycle logic
- Smoke test after every change — verify in running browser at localhost:47178
- Handle errors explicitly — no silent failures
- Every function gets a docstring
- Comment the "why" for non-obvious decisions

### Workflow
- Plan mode FIRST — propose approach and get approval before writing code
- One task at a time — document side issues, don't fix inline
- Update LEARNINGS.md after every task if gotchas discovered
- Never start serious dev without a task doc

### Architecture
- Follow existing patterns — check the codebase first
- No new dependencies without discussion
- Database changes need Alembic migrations
- Frontend displays, backend computes — ALL projection calculations run server-side
- French locale everywhere — i18n keys, no hardcoded strings
- Dark theme only (zinc-950 base) — prototype is the style guide

### Calculation Rules (CRITICAL)
- NUMERIC(12,2) in DB, never FLOAT
- All money as Decimal in Python, never float
- Inflation compounds: `base * (1 + rate) ** years`
- AE cotisation rates are TIME-DEPENDENT — use the rate schedule, not a flat rate
- Round at display time only, not during intermediate steps
- Test projections against hand-calculated examples

### Life Entity Rules
- Every entity (kid, pet, car, tech) has an age and a cost lifecycle
- Costs are time-bounded: `from_age` → `to_age` for kids, `replace_cycle` for assets
- Canned defaults are starting points — user ALWAYS overrides
- Progressive calculations: the engine must know WHEN costs start/stop/change
- LLM suggestions are advisory — user confirms before anything affects projections

### Frontend Conventions
- ALL text via i18n keys — hierarchical: `runway.chart.title`
- Design tokens in `design-tokens.css` (dark theme: zinc/teal/amber palette)
- Sidebar nav, not tabs — prototype layout is canonical
- Input pattern: label above, suffix inside, hint below
- Cards with accent border-left for section grouping
- Charts: simple area/line only (SVG), no chart libraries needed for MVP

## Definition of Done

| Change type | Rebuild command | Then verify |
|---|---|---|
| Frontend source | `docker compose build frontend && docker compose up -d frontend` | Hard-refresh at :47178 |
| Frontend packages | `docker compose build frontend && docker compose up -d -V frontend` | Check logs |
| Backend source | `docker compose up -d --build backend` | Check logs |
| Alembic migration | `docker compose exec -w /app -e PYTHONPATH=/app backend alembic upgrade head` | Check logs |
```

---

## Sprint Plan

### Sprint 0: Fork & Strip
**Goal:** Fork ComCoi, remove salon domain, keep infrastructure. Clean slate for Horizon 30.
**Tasks: 6 · Priority: ALL P0**

### Sprint 1: Data Model & Identity
**Goal:** User profile, life entity schemas, projection config. The "Identité" and "Revenus" sections.
**Tasks: 8**

### Sprint 2: Expense Engine & Life Entities
**Goal:** Monthly expenses, kids/pets/cars/tech lifecycle models, recurring punctual. The "Charges" and "Vie" sections.
**Tasks: 10**

### Sprint 3: Savings & Projects
**Goal:** Investment vehicle tracking, project P&Ls, status change simulation. "Épargne" and "Projets" sections.
**Tasks: 8**

### Sprint 4: Projection Engine & Runway
**Goal:** The 30-year calculation engine, charts, milestones, goal tracking. The "Horizon" section.
**Tasks: 10**

### Sprint 5: Progressive Automation & AI
**Goal:** LLM-powered lifecycle suggestions, smart defaults, scenario analysis.
**Tasks: 6**

---

## SPRINT 0 — Fork & Strip

**Status:** BACKLOG
**Goal:** Clean ComCoi fork → Horizon 30 shell with working auth, DB, Docker, i18n.

---

### TASK-0.1: Fork Repository & Rename

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 30 min
**Dependencies:** None

#### Context
Fork the ComCoi repo. Rename all top-level references (package.json, docker-compose, README, meta.json) from ComCoi/Atlas to Horizon 30. Keep the full Docker infrastructure, auth system, and build pipeline.

#### Requirements
1. Fork repo to new GitHub repo `horizon30`
2. Update `package.json` name, `docker-compose.yml` service names
3. Update `frontend/src/config/meta.json` — app name, description
4. Update README.md with Horizon 30 context
5. Verify `docker compose up -d` still works after rename

#### Acceptance Criteria
- [ ] Repo builds and runs with `docker compose up -d`
- [ ] Login page shows "Horizon 30" branding
- [ ] No references to "Communauté Coiffure" or "Atlas" in user-facing strings

---

### TASK-0.2: Strip Salon Domain Models

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 2 hr
**Dependencies:** TASK-0.1

#### Context
Remove all salon-specific SQLAlchemy models, Alembic migrations, API routes, and services. Keep: users, auth, admin_config, stripe infrastructure. The goal is a clean DB with just auth + user profile.

#### Requirements
1. Remove models: `salons`, `salon_config`, `employees`, `monthly_reports`, `monthly_salaries`, `expenses`, `services`, `monthly_services`, `payslip_*`, `coco_*`, `brand_purchases`, `calculation_history`, `scenarios`
2. Remove corresponding routers, services, schemas
3. Remove `backend/app/calculations/` entirely (will be rebuilt)
4. Create fresh Alembic migration that creates only: `users`, `admin_config`, `stripe_events_processed`
5. Keep `backend/app/services/auth.py` and Stripe webhook handler

#### Acceptance Criteria
- [ ] `alembic upgrade head` creates clean schema
- [ ] Auth endpoints work (register, login, reset password)
- [ ] No import errors in backend
- [ ] `docker compose up -d` runs clean

---

### TASK-0.3: Strip Salon Frontend Routes

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 2 hr
**Dependencies:** TASK-0.1

#### Context
Remove all `(app)/` routes that are salon-specific. Keep: auth routes, public landing shell, admin shell. Replace the app layout with the Horizon 30 sidebar nav from the prototype.

#### Requirements
1. Remove routes: `pilotage/`, `mon-mois-typique/`, `parametrage/`, `calculateurs/`, `tableau-de-bord/`
2. Keep route groups: `(auth)/`, `(public)/`, `(admin)/`
3. Create new `(app)/` layout with sidebar nav matching prototype (7 sections)
4. Create placeholder pages for each section: identity, revenue, expenses, life, savings, projects, runway
5. Apply dark theme design tokens (zinc-950 base, teal accent)

#### Acceptance Criteria
- [ ] Sidebar nav renders with 7 sections
- [ ] Each section shows a placeholder page
- [ ] Dark theme applied consistently
- [ ] Auth flow still works (login → app shell)

---

### TASK-0.4: Dark Theme Design Tokens

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 1 hr
**Dependencies:** TASK-0.3

#### Context
Replace ComCoi's warm light theme with Horizon 30's dark fintech theme from the prototype. Update `design-tokens.css` with the new palette.

#### Requirements
1. Background: `zinc-950` (#09090b)
2. Card background: `zinc-900/40` with `zinc-800/60` borders
3. Primary accent: teal-400 (#2dd4bf) for CTAs and active states
4. Secondary accents: amber-400 (warnings), rose-400 (negative), emerald-400 (positive), purple-400 (savings)
5. Text: white primary, zinc-400 secondary, zinc-500 tertiary
6. Font: Inter for UI, JetBrains Mono for numbers/financial data
7. Card pattern: `border-l-2` accent color for section grouping
8. Input pattern: `bg-zinc-900/60 border-zinc-700/40` with teal focus ring

#### Acceptance Criteria
- [ ] All placeholder pages use dark theme consistently
- [ ] No ComCoi purple/gold remnants
- [ ] Fonts loaded via Google Fonts
- [ ] CSS custom properties defined for all tokens

---

### TASK-0.5: i18n Reset

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 30 min
**Dependencies:** TASK-0.3

#### Context
Strip ComCoi French strings from `fr.json`, keep the i18n infrastructure. Add initial Horizon 30 keys for nav, section titles, and common labels.

#### Requirements
1. Clear `fr.json` and `en.json` of salon-specific keys
2. Add keys for: nav labels, section titles, common financial terms (CA, cotisations, patrimoine, etc.)
3. Keep i18n loading mechanism and `$t()` helper

#### Acceptance Criteria
- [ ] Nav labels render from i18n keys
- [ ] No hardcoded French strings in components
- [ ] `$t('nav.identity')` → "Identité"

---

### TASK-0.6: Prototype Reference Doc

**Status:** BACKLOG
**Priority:** P2
**Est. effort:** 30 min
**Dependencies:** None

#### Context
Copy the prototype JSX into `dev-docs/prototype/` and write a reference doc that maps prototype sections to planned routes and components.

#### Requirements
1. Copy prototype to `dev-docs/prototype/horizon30.jsx`
2. Create `dev-docs/PROTOTYPE_REFERENCE.md` mapping each prototype section to planned route/component
3. Document the design decisions: sidebar nav, card patterns, input patterns, chart approach, stat card layout

#### Acceptance Criteria
- [ ] Prototype file committed
- [ ] Reference doc covers all 7 sections
- [ ] Screenshots or section descriptions for each

---

## SPRINT 1 — Data Model & Identity

**Status:** BACKLOG
**Goal:** User financial profile, AE configuration, revenue tracking foundation.

---

### TASK-1.1: User Profile Model

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 1 hr
**Dependencies:** TASK-0.2

#### Context
The core data model for Horizon 30 — a user's financial identity. This replaces the salon/salon_config models.

#### Requirements
1. Create `UserProfile` model:
   - `user_id` FK → users (unique)
   - `birth_date` DATE — used to derive current age
   - `target_retirement_age` INTEGER default 67
   - `tax_parts` NUMERIC(3,1) default 1.0
   - `status` VARCHAR(20) — ae, eirl, eurl, sasu
   - `ae_activity_type` VARCHAR(50) — bic_vente, bic_services, bnc_non_reglementee, bnc_cipav
   - `has_versement_liberatoire` BOOLEAN default false
   - `monthly_gross_ca` NUMERIC(10,2)
   - `growth_preset` VARCHAR(20) — conservative, moderate, ambitious, custom
   - `growth_rate_custom` NUMERIC(5,4) — only when preset=custom
   - `cesu_annual` NUMERIC(10,2) default 0
   - `charity_annual` NUMERIC(10,2) default 0
   - `caf_override_monthly` NUMERIC(10,2) nullable — null = auto-estimate
   - `monthly_revenue_goal` NUMERIC(10,2) nullable
   - `world_scale` VARCHAR(20) default 'moderate' — optimistic, moderate, pessimistic
2. Create Pydantic Read/Write schemas
3. Create CRUD router at `/api/profile`
4. Alembic migration

#### Acceptance Criteria
- [ ] Migration runs clean
- [ ] GET/PUT `/api/profile` works
- [ ] Unit tests for schema validation

---

### TASK-1.2: AE Cotisation Rate Schedule

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 1 hr
**Dependencies:** None

#### Context
AE cotisation rates are NOT flat — they increase over time due to legislation. The projection engine needs a time-dependent rate lookup. This is critical for accuracy over 30 years.

#### Requirements
1. Create `backend/app/calculations/ae_rates.py`
2. Store rate schedule as a Python dict (not DB — changes need code review):
   ```python
   AE_RATE_SCHEDULE = {
       "bnc_non_reglementee": [
           {"from_year": 2026, "rate": Decimal("0.262")},
           {"from_year": 2027, "rate": Decimal("0.268")},
           # ... projected
       ],
       # ... other types
   }
   ```
3. Function `get_ae_rate(activity_type: str, year: int) -> Decimal`
4. Function `get_rate_schedule(activity_type: str) -> list[dict]` for frontend display
5. API endpoint `GET /api/rates/ae-schedule?type=bnc_non_reglementee`
6. Unit tests against known 2026 rates

#### Acceptance Criteria
- [ ] `get_ae_rate("bnc_non_reglementee", 2026)` returns `Decimal("0.262")`
- [ ] `get_ae_rate("bnc_non_reglementee", 2030)` returns projected rate
- [ ] API returns schedule for frontend
- [ ] Tests pass

---

### TASK-1.3: Monthly Expense Model

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 1 hr
**Dependencies:** TASK-1.1

#### Context
Base monthly expenses for 2026 that get inflation-adjusted in projections. Stored as a JSON column (flexible categories) rather than rigid columns.

#### Requirements
1. Add `monthly_expenses` JSONB column to `UserProfile`:
   ```json
   {
     "loyer": 800, "energie": 120, "internet": 60,
     "assurance": 100, "transport": 200, "alimentation": 400,
     "sante": 50, "loisirs": 150, "abonnements": 50,
     "impots": 100, "credit": 0, "divers": 100
   }
   ```
2. Pydantic schema with validation (all values >= 0)
3. GET/PUT endpoint for expenses
4. Frontend: Expenses section with grid of inputs matching prototype

#### Acceptance Criteria
- [ ] Expenses save and load correctly
- [ ] Frontend renders expense grid
- [ ] Total computed and displayed

---

### TASK-1.4: Identity Frontend Section

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 2 hr
**Dependencies:** TASK-1.1, TASK-0.4

#### Context
The first section users see. Maps directly to the prototype's Identity section — birth date, target age, parts fiscales, AE status, VL toggle, cotisation rate preview.

#### Requirements
1. Create `(app)/identity/+page.svelte` and `+page.server.ts`
2. Load user profile on mount, auto-save on change (debounce 800ms)
3. Two cards: "Vous" (age, target, parts) and "Statut & Activité" (status, type, VL, rate preview)
4. Rate schedule preview component showing projected rates
5. All text via i18n keys
6. Match prototype layout exactly

#### Acceptance Criteria
- [ ] Profile saves to backend on input change
- [ ] Rate schedule renders for selected AE type
- [ ] VL toggle updates displayed rate
- [ ] Dark theme, prototype layout match

---

### TASK-1.5: Revenue Frontend Section

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 2 hr
**Dependencies:** TASK-1.1, TASK-1.2

#### Context
The Revenue section — CA input, growth preset selector, 5-year preview, CESU/charity tax breaks. Maps to prototype's Revenue section.

#### Requirements
1. Create `(app)/revenue/+page.svelte`
2. Stats row: CA brut, cotisations, net (computed from profile + rates)
3. Growth preset cards (conservative/moderate/ambitious/custom) with descriptions
4. 5-year CA preview computed client-side from growth rate
5. CESU & charity inputs with live credit calculation display
6. Info box explaining CESU tax credit

#### Acceptance Criteria
- [ ] Growth preset selection updates stored preference
- [ ] 5-year preview reacts to CA and growth changes
- [ ] CESU credit shows calculated savings
- [ ] Stats row shows correct cotisation amount

---

### TASK-1.6: Expenses Frontend Section

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 1.5 hr
**Dependencies:** TASK-1.3

#### Context
Monthly expense grid with inflation preview table. Maps to prototype's Expenses section.

#### Requirements
1. Create `(app)/expenses/+page.svelte`
2. Stats row: total monthly, total annual
3. 3-column input grid for expense categories
4. Inflation preview table: 3 scales × 4 time horizons (+5/10/20/30 years)
5. CAF override input with hint about auto-estimation
6. Info text explaining inflation is applied in Horizon tab

#### Acceptance Criteria
- [ ] Expenses save to backend
- [ ] Inflation table computes correctly for all 3 scales
- [ ] Total updates reactively

---

### TASK-1.7: Inflation Scale Constants

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 30 min
**Dependencies:** None

#### Context
Three economic scenarios used throughout projections. Defined server-side for consistency.

#### Requirements
1. Create `backend/app/calculations/scales.py`:
   ```python
   SCALES = {
       "optimistic":  {"inflation": Decimal("0.018"), "cost_living": Decimal("0.020")},
       "moderate":    {"inflation": Decimal("0.025"), "cost_living": Decimal("0.030")},
       "pessimistic": {"inflation": Decimal("0.035"), "cost_living": Decimal("0.045")},
   }
   ```
2. API endpoint `GET /api/scales`
3. Used by projection engine and frontend inflation preview

#### Acceptance Criteria
- [ ] API returns all 3 scales
- [ ] Values match prototype

---

### TASK-1.8: Growth Preset Constants

**Status:** BACKLOG
**Priority:** P2
**Est. effort:** 30 min
**Dependencies:** None

#### Context
Revenue growth presets with labels and descriptions.

#### Requirements
1. Add to `backend/app/calculations/growth.py`:
   - conservative: 1%/yr
   - moderate: 3%/yr
   - ambitious: 6%/yr
   - custom: user-defined
2. API endpoint `GET /api/growth-presets`
3. Each preset has: key, label, rate, description (French)

#### Acceptance Criteria
- [ ] API returns presets with descriptions
- [ ] Frontend renders preset cards from API data

---

## SPRINT 2 — Life Entities

**Status:** BACKLOG
**Goal:** Kids, pets, cars, tech — each with lifecycle cost models. The progressive calculation system.

---

### TASK-2.1: Life Entity Base Model

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 1.5 hr
**Dependencies:** TASK-1.1

#### Context
All life entities share a pattern: they belong to a user, have a name, a type, a birth/acquisition date (from which age is derived), and a set of cost events. The model should be flexible enough to handle kids, pets, cars, and tech with one table + a JSONB cost_events column.

#### Requirements
1. Create `LifeEntity` model:
   - `id` UUID PK
   - `user_id` FK → users
   - `entity_type` VARCHAR(20) — kid, pet, car, tech
   - `name` VARCHAR(100)
   - `birth_or_acquisition_date` DATE — age derived from this
   - `metadata` JSONB — type-specific fields (pet_type, car_fuel, tech_model, etc.)
   - `cost_events` JSONB — array of cost event objects
   - `is_active` BOOLEAN default true
   - `created_at`, `updated_at` TIMESTAMPTZ
2. Cost event schema:
   ```json
   {
     "label": "Crèche",
     "from_age": 0, "to_age": 3,
     "amount": 500,
     "frequency": "monthly",  // or "annual" or "once"
     "is_canned": true,       // system-suggested vs user-created
     "source": "default"      // "default", "user", "ai_suggested"
   }
   ```
3. CRUD router at `/api/life-entities`
4. Pydantic schemas with validation per entity_type

#### Acceptance Criteria
- [ ] Migration runs
- [ ] CRUD endpoints work for all 4 entity types
- [ ] Cost events validate correctly
- [ ] Unit tests for create/read/update/delete

#### Technical Notes
**Progressive calculation concept:** When a user adds a kid with age 1, the system pre-populates cost_events based on canned French defaults:
- 0→3: crèche (~500€/month, adjustable)
- 3→6: maternelle (cantine ~100€/month)
- 6→11: primaire (cantine + périscolaire ~150€/month, camp d'été ~800€/year)
- 11→15: collège (cantine ~150€/month, extras ~100€/month)
- 15→18: lycée (fournitures ~600€/year, extras)
- 18: permis + first car (~5000€ one-time)
- 18→23: études supérieures (~500€/month)

The user's kid's current age determines which events are "active" vs "future" vs "past". The birth month matters for school entry (September rule in France). The projection engine walks each entity's cost_events for each year.

---

### TASK-2.2: Canned Defaults Service

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 2 hr
**Dependencies:** TASK-2.1

#### Context
When a user adds a life entity, the system should pre-populate reasonable cost events they can tweak. This is the "progressive calculation" foundation — the system knows that a 1-year-old in France will enter école maternelle at ~3 based on their birth month (September cutoff).

#### Requirements
1. Create `backend/app/services/canned_defaults.py`
2. `get_kid_defaults(birth_date: date) -> list[CostEvent]` — calculates school entry year based on September rule, populates age-appropriate expenses
3. `get_pet_defaults(pet_type: str, age: int) -> list[CostEvent]` — vaccination schedule, annual vet, food, grooming (for dogs), higher costs for young (<2) and old (>10) animals
4. `get_car_defaults(fuel_type: str, age: int) -> list[CostEvent]` — annual running costs (insurance, fuel, maintenance), CT every 2 years after age 4, replacement at cycle end
5. `get_tech_defaults(device_type: str) -> list[CostEvent]` — replacement cycle based on device type (phone: 3yr, laptop: 4yr, tablet: 5yr), cost projections with inflation
6. All defaults are clearly labeled `is_canned: true, source: "default"` so the user knows what's system-suggested vs manually added
7. Unit tests comparing defaults against expected French costs

#### Acceptance Criteria
- [ ] Adding a kid born 2025-03-15 generates crèche through études with correct age ranges
- [ ] September rule: kid born in October starts maternelle a year later than kid born in August
- [ ] Pet costs increase for ages < 2 and > (lifespan - 3)
- [ ] Car CT events appear every 2 years starting age 4
- [ ] All amounts are reasonable (verified against French cost-of-living data)

---

### TASK-2.3: Life Entity Frontend — Kids

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 2 hr
**Dependencies:** TASK-2.1, TASK-2.2

#### Context
The kid section of the "Vie" tab. Each kid shows as an expandable card with their cost events, color-coded by active/future/past. Maps to prototype's Life section.

#### Requirements
1. Create `(app)/life/+page.svelte` with kid section
2. "Add kid" button → name + birth date → backend creates entity with canned defaults
3. Each kid card shows:
   - Name, age (derived from birth date)
   - Cost events list with active/future/past visual indicators (purple dot = active, grey = future, faded = past)
   - Inline editing of amounts, labels, age ranges
   - "Add custom expense" button
4. Auto-save on change (debounce 800ms)
5. Remove button with confirmation

#### Acceptance Criteria
- [ ] Adding a kid auto-populates cost events
- [ ] Active/future/past visual states correct based on kid's current age
- [ ] Editing an amount saves to backend
- [ ] Adding custom expense works
- [ ] Removing a kid works with confirmation

---

### TASK-2.4: Life Entity Frontend — Pets, Cars, Tech

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 2 hr
**Dependencies:** TASK-2.1, TASK-2.2

#### Context
The remaining life entity sections. Simpler than kids — fewer cost events, more focused on replacement cycles.

#### Requirements
1. Add pet section to life page: name, type (dog/cat/other), birth date, annual cost, canned vet/vaccine events
2. Add car section: name, fuel type, acquisition date, annual running cost, replacement cycle + cost, auto-generate CT events
3. Add tech section: name (e.g. "MacBook Pro"), acquisition date, replacement cycle, estimated replacement cost
4. Each section matches prototype layout (inline inputs, remove button)
5. All canned defaults populated on creation

#### Acceptance Criteria
- [ ] Each entity type creates with correct defaults
- [ ] Replacement cycles generate future one-time cost events
- [ ] Car CT events auto-generated
- [ ] All sections render in prototype style

---

### TASK-2.5: Recurring Punctual Expenses

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 1 hr
**Dependencies:** TASK-1.1

#### Context
Expenses that recur annually but have a start and end date — loan repayments, annual holiday budget, kid's summer camp subscription. Separate from life entities because they're user-defined time-bounded costs.

#### Requirements
1. Create `RecurringExpense` model:
   - `user_id`, `label`, `annual_amount` NUMERIC(10,2)
   - `from_year` INTEGER, `to_year` INTEGER
   - `category` VARCHAR(50) nullable — for grouping
2. CRUD router `/api/recurring-expenses`
3. Frontend section in Life tab matching prototype (description, amount, from year, to year)

#### Acceptance Criteria
- [ ] CRUD works
- [ ] Frontend renders inline add/edit/remove
- [ ] Projection engine can query these per year

---

## SPRINT 3 — Savings & Projects

**Status:** BACKLOG
**Goal:** Investment vehicle tracking, project P&Ls, status change simulation.

---

### TASK-3.1: Investment Vehicle Model

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 1.5 hr
**Dependencies:** TASK-1.1

#### Context
Track existing balances and monthly allocations across French investment vehicles (Livret A, LDDS, AV, PEA, SCPI, PER). Vehicle specs (rates, ceilings, tax treatment) are constants; user data is balances + monthly contributions.

#### Requirements
1. Create `InvestmentAllocation` model:
   - `user_id` FK
   - `vehicle_key` VARCHAR(20) — livret_a, ldds, av_euro, av_uc, pea, scpi, per
   - `existing_balance` NUMERIC(12,2) default 0
   - `monthly_contribution` NUMERIC(10,2) default 0
2. Vehicle specs in `backend/app/calculations/vehicles.py` (rate, tax_free, tax_rate, ceiling, risk label)
3. API: `GET/PUT /api/investments` — returns all vehicles with user allocations
4. Frontend: Savings section matching prototype (vehicle cards with balance + monthly inputs)

#### Acceptance Criteria
- [ ] All 7 vehicle types accessible
- [ ] Balance and contribution save correctly
- [ ] Vehicle specs served via API for frontend display
- [ ] Ceiling warnings shown when balance approaches limit

---

### TASK-3.2: Project Model (Investment & Life Event)

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 1.5 hr
**Dependencies:** TASK-1.1

#### Context
Two project types: investments (gîte, rental property — ongoing income/expenses) and life events (wedding, big trip — one-time costs). Each investment has a mini P&L.

#### Requirements
1. Create `Project` model:
   - `user_id`, `project_type` VARCHAR(20) — "invest" or "event"
   - `label` VARCHAR(200)
   - For invest: `start_year`, `purchase_cost`, `annual_income`, `annual_expenses`, `tax_rate` NUMERIC(5,3)
   - For event: `event_year`, `cost`
   - `is_active` BOOLEAN default true
2. CRUD router `/api/projects`
3. Frontend: Projects section with investment cards (mini P&L display: net, taxed net, yield %) and event list

#### Acceptance Criteria
- [ ] Both project types create/read/update/delete
- [ ] Investment P&L computed server-side: `(income - expenses) * (1 - tax_rate)`
- [ ] Frontend displays yield percentage
- [ ] Life events show in timeline

---

### TASK-3.3: Status Change Simulation

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 1 hr
**Dependencies:** TASK-1.1

#### Context
"What if I switch from AE to EIRL in 2028?" — stores the planned status change and estimated annual savings. The projection engine applies the savings from the change year onward.

#### Requirements
1. Add to `UserProfile`:
   - `status_change_enabled` BOOLEAN default false
   - `status_change_year` INTEGER nullable
   - `status_change_target` VARCHAR(20) nullable
   - `status_change_savings` NUMERIC(10,2) nullable — annual net savings vs staying AE
2. Frontend: section in Projects tab with enable toggle, year, target status, savings input
3. Info text explaining the EIRL deduction logic (from prototype)

#### Acceptance Criteria
- [ ] Toggle enables/disables simulation
- [ ] Values save to profile
- [ ] Projection engine reads these for runway calculation

---

## SPRINT 4 — Projection Engine & Runway

**Status:** BACKLOG
**Goal:** The core 30-year calculation engine and the Horizon dashboard.

---

### TASK-4.1: Projection Engine — Core

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** Half day
**Dependencies:** TASK-1.2, TASK-1.3, TASK-2.1, TASK-3.1, TASK-3.2

#### Context
The heart of Horizon 30. Takes all user data and produces a year-by-year projection from current age to target retirement age. This is a pure calculation — no DB writes, just reads all the data and computes.

#### Requirements
1. Create `backend/app/calculations/projection.py`
2. Function `project_timeline(user_id: UUID, scale: str) -> list[YearProjection]`
3. For each year in the range:
   - Compute gross CA with growth rate
   - Look up AE rate for that year (time-dependent!)
   - Compute base expenses with cost-of-living inflation
   - Walk all life entities: compute cost events active for that year, inflation-adjusted
   - Walk recurring expenses: include if year in range
   - Walk projects: include income/expenses for investments, costs for events
   - Compute CAF based on kids under 20 + income
   - Compute CESU/charity tax credits
   - Apply status change savings if enabled and year >= change year
   - Compute net annual
   - Walk investment allocations: compound balances with returns (net of tax where applicable)
   - Compute total wealth and passive income (4% rule)
   - Check goal reached (total monthly income + passive >= goal)
4. Return `list[YearProjection]` with all intermediate values

#### YearProjection schema:
```python
class YearProjection(BaseModel):
    year: int
    age: int
    gross_annual: Decimal
    ae_rate: Decimal
    charges: Decimal
    base_expenses: Decimal
    kid_expenses: Decimal
    pet_expenses: Decimal
    car_expenses: Decimal
    tech_expenses: Decimal
    recurring_expenses: Decimal
    project_expenses: Decimal
    project_income: Decimal
    caf: Decimal
    tax_credits: Decimal
    net_annual: Decimal
    year_invested: Decimal
    year_returns: Decimal
    total_wealth: Decimal
    passive_monthly: Decimal
    total_monthly_income: Decimal
    goal_reached: bool
```

#### Acceptance Criteria
- [ ] Projection computes for 30 years without error
- [ ] AE rates change over time (not flat)
- [ ] Kid expenses appear and disappear at correct ages
- [ ] Car replacement costs appear at correct intervals
- [ ] Investment balances compound correctly
- [ ] Wealth at year 30 matches hand-calculated example
- [ ] Unit tests with at least 3 scenarios (bare minimum, moderate, aggressive)

---

### TASK-4.2: Projection API Endpoint

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 1 hr
**Dependencies:** TASK-4.1

#### Context
Expose the projection engine via API. The frontend calls this to render the Runway tab.

#### Requirements
1. `GET /api/projection?scale=moderate` → returns full timeline
2. Also returns: milestones (100k, 250k, 500k, 1M), goal_reached_year, summary stats
3. Response cached in memory for 30 seconds (invalidate on profile/entity/allocation change)
4. Performance target: < 500ms for 30-year projection

#### Acceptance Criteria
- [ ] Returns correct timeline for all 3 scales
- [ ] Milestones computed correctly
- [ ] Response time < 500ms

---

### TASK-4.3: Runway Frontend — Charts & Stats

**Status:** BACKLOG
**Priority:** P0
**Est. effort:** 2 hr
**Dependencies:** TASK-4.2

#### Context
The main Horizon tab. Scale selector, goal input, hero stats, wealth chart, income chart, milestones.

#### Requirements
1. Create `(app)/runway/+page.svelte`
2. Scale selector (3 buttons: optimiste/modéré/pessimiste)
3. Goal input with live "achieved in year X" hint
4. Hero stat cards: wealth at target age, passive monthly
5. Wealth trajectory chart (SVG area chart, teal)
6. Total income chart (SVG area chart, emerald) with goal line (amber dashed)
7. Milestone timeline (vertical dots with labels)
8. Auto-refresh projection when scale or goal changes

#### Acceptance Criteria
- [ ] Charts render correctly from projection data
- [ ] Scale toggle recomputes projection
- [ ] Goal line renders on income chart
- [ ] Milestones appear when wealth crosses thresholds

---

### TASK-4.4: Runway Frontend — Detailed Table

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 1 hr
**Dependencies:** TASK-4.2

#### Context
The detailed projection table showing every 5 years. Matches prototype exactly.

#### Requirements
1. Table with columns: Year, Age, CA brut, Cotisations, Cotis.%, Vie, Enfants, Projets, Net, Patrimoine, Passif/mois
2. Show every 5th year + final year
3. Color coding: teal for net positive, rose for negative, emerald for passive income
4. Horizontal scroll on mobile

#### Acceptance Criteria
- [ ] Table renders with correct data
- [ ] Color coding applied
- [ ] Responsive on mobile

---

### TASK-4.5: Runway Frontend — Insights

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 1 hr
**Dependencies:** TASK-4.2

#### Context
Contextual insights at the bottom of the Runway tab — "Goal reached", "Gap to close", "Disclaimer".

#### Requirements
1. Green card if passive income >= goal: "Objectif atteint" message
2. Amber card if not: "Gap à combler" with actionable suggestions
3. Grey disclaimer card (always shown)
4. Insights react to scale changes

#### Acceptance Criteria
- [ ] Correct insight shown based on projection outcome
- [ ] Suggestions are relevant (increase savings, add project, change status)
- [ ] Disclaimer always present

---

## SPRINT 5 — Progressive Automation & AI

**Status:** BACKLOG
**Goal:** LLM-assisted lifecycle predictions, smart suggestions, scenario analysis.

---

### TASK-5.1: AI Lifecycle Suggestions

**Status:** BACKLOG
**Priority:** P1
**Est. effort:** 2 hr
**Dependencies:** TASK-2.1, TASK-2.2

#### Context
When a user adds a life entity, optionally invoke Claude to suggest cost events they might not have thought of. Example: adding a dog → "Have you thought about spaying (~300€ at age 1), annual teeth cleaning (~200€/year after age 5), pet insurance (~30€/month)?"

#### Requirements
1. Create `backend/app/services/ai_suggestions.py`
2. Function `suggest_cost_events(entity: LifeEntity) -> list[SuggestedCostEvent]`
3. Calls Claude Sonnet with entity context, asks for missing cost events
4. System prompt enforces: French costs, realistic amounts, never give financial advice, label as "ai_suggested"
5. Frontend: after adding entity, show suggestions as dismissible cards ("Add this?" / "Ignore")
6. Accepted suggestions become regular cost_events with `source: "ai_suggested"`

#### Acceptance Criteria
- [ ] Suggestions are relevant and realistic
- [ ] User can accept or dismiss each suggestion
- [ ] Accepted suggestions appear in cost events
- [ ] No hallucinated financial advice

---

### TASK-5.2: AI Scenario Analysis

**Status:** BACKLOG
**Priority:** P2
**Est. effort:** 2 hr
**Dependencies:** TASK-4.1

#### Context
"Explain my runway" button that sends the projection summary to Claude and gets a plain-language analysis. Not financial advice — just pattern recognition and "have you considered" suggestions.

#### Requirements
1. Button on Runway tab: "Analyser mon horizon"
2. Sends projection summary (not raw data) to Claude
3. Claude responds with: what's working, what the risks are, what levers the user could pull
4. Displayed as a card on the Runway tab
5. Disclaimer: "This is not financial advice"

#### Acceptance Criteria
- [ ] Analysis generates in < 10 seconds
- [ ] Response is in French, plain language
- [ ] No specific financial advice given
- [ ] Disclaimer always shown

---

## Notes for Cline Execution

### Key Principles from the Prototype

1. **Progressive lifecycle calculation**: When I add my 1-year-old, the system knows that in ~2 years (based on birth month and the September rule) she enters maternelle. Crèche costs stop. Cantine costs start. Summer camp costs start at age 6. Each cost event has a clear start age and end age. The projection engine walks these per year.

2. **Everything inflation-adjusts**: Base expenses, life entity costs, car replacement costs, tech costs — all compound with the selected inflation scale. The user sets 2026 values, the engine handles the rest.

3. **Cotisation rates are time-dependent**: Richard pays ~26.2% now. The projection uses different rates for 2028, 2030, 2035 based on legislative trends. This is a lookup table, not a flat value.

4. **Goal-based tracking**: The user sets a monthly income target for retirement. The Runway shows when their total income (work + passive + project income) crosses that line. The goal line appears on the chart.

5. **Configure once, live on the Runway**: Identity/Revenue/Expenses/Life/Savings/Projects are configuration. The Horizon tab is where you spend your time — watching the numbers, tweaking scenarios, setting goals.

### Prototype File Reference
The prototype at `dev-docs/prototype/horizon30.jsx` is the UX source of truth for:
- Sidebar nav layout and section icons
- Card component styling (border-l accent, zinc-900/40 bg)
- Input component styling (zinc-900/60 bg, teal focus ring)
- Stat card layout (9px label, lg mono value, 10px sub)
- Chart styling (SVG area charts with gradient fills)
- Scale selector (3-button bar)
- Growth preset cards (4-card grid with descriptions)
- Life entity cost event list (active/future/past visual states)
- Milestone timeline (vertical dots)
- Detailed table (every 5th year, color-coded columns)
