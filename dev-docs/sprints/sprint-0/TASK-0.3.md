# TASK-0.3: Strip Salon Domain — Frontend

**Status:** DONE ✅ (2026-05-08)
**Sprint:** 0
**Priority:** P0 (critical)
**Est. effort:** 2 hr
**Dependencies:** TASK-0.1

## Context

The ComCoi frontend has ~30 routes and ~50 components specific to salon management (pilotage, mon-mois-typique, paramétrage, calculateurs, tableau-de-bord, CoCo AI assistant). Horizon 30 replaces all of this with a sidebar-nav app shell and 7 section placeholder pages.

This task is independent of TASK-0.2 (backend strip) — the frontend will initially show broken pages where API calls fail, but that's fine because we're replacing them with placeholders anyway.

## Requirements

1. **Remove these route directories** inside `frontend/src/routes/(app)/`:
   - `pilotage/`
   - `mon-mois-typique/`
   - `parametrage/`
   - `calculateurs/`
   - `tableau-de-bord/`
   - Any other salon-specific routes

2. **Keep these route groups:**
   - `(auth)/` — login, register, reset password
   - `(public)/` — landing page shell (will be rethemed later)
   - `(admin)/` — admin shell (useful for config management)

3. **Replace `(app)/+layout.svelte`** with new Horizon 30 layout:
   - Sidebar nav on the left (w-44, sticky, dark theme)
   - 7 nav items: Identité (◉), Revenus (◈), Charges (▤), Vie (♦), Épargne (◆), Projets (⚡), Horizon (→)
   - Active state: `bg-zinc-800/60 text-white`
   - Inactive: `text-zinc-500 hover:text-zinc-300`
   - Quick stats panel below nav (CA/mois, Enfants, Épargne/mois, Projets)
   - Main content area to the right with `py-5 px-6`
   - Header bar: Horizon 30 logo (teal gradient H), app name, age→target subtext
   - Reference: prototype `horizon30.jsx` SECTIONS array and sidebar layout

4. **Create 7 placeholder pages** in `(app)/`:
   - `identity/+page.svelte`
   - `revenue/+page.svelte`
   - `expenses/+page.svelte`
   - `life/+page.svelte`
   - `savings/+page.svelte`
   - `projects/+page.svelte`
   - `runway/+page.svelte`
   - Each placeholder: section title, brief description, "Coming in Sprint 1/2/3/4" note

5. **Remove salon-specific components** from `frontend/src/lib/components/`:
   - Anything prefixed with or specifically for: Salon, Employee, MonthlyReport, Payslip, CoCo, Calculator, Dashboard, MobileYearFeed, etc.
   - **KEEP** generic components: InfoBubble, Modal, Toast, LoadingSpinner, any layout primitives

6. **Remove salon-specific stores** from `frontend/src/lib/stores/`:
   - salon.ts, employees.ts, etc.
   - **KEEP** auth.ts, user.ts, i18n.ts, any generic stores

7. **Remove `frontend/src/lib/coco/`** — the AI assistant client (will be rebuilt for Horizon 30)

8. **Update `(app)/+layout.server.ts`** — remove salon data loading, keep auth guard

## Technical Approach

### Files to Create/Modify
- `frontend/src/routes/(app)/+layout.svelte` — full rewrite with sidebar nav
- `frontend/src/routes/(app)/+layout.server.ts` — strip salon loading, keep auth
- Create 7 new `+page.svelte` files (placeholders)
- Delete: ~25-30 files across routes, components, stores

### Layout Structure (from prototype)
```svelte
<div class="min-h-screen bg-zinc-950 text-white">
  <!-- Header -->
  <header class="border-b border-zinc-800/50 bg-zinc-950/95 backdrop-blur sticky top-0 z-50">
    <!-- Logo + app name + age range -->
  </header>

  <div class="max-w-6xl mx-auto flex">
    <!-- Sidebar -->
    <nav class="w-44 flex-shrink-0 border-r border-zinc-800/40 min-h-[calc(100vh-56px)] py-4 px-3 sticky top-14 self-start">
      <!-- Nav items -->
      <!-- Quick stats -->
    </nav>

    <!-- Content -->
    <main class="flex-1 py-5 px-6 min-w-0">
      <slot />
    </main>
  </div>
</div>
```

## Acceptance Criteria

- [ ] `docker compose build frontend && docker compose up -d frontend` builds without errors
- [ ] Browser at localhost:47178 → login → app shell renders
- [ ] Sidebar nav shows 7 sections with correct labels and icons
- [ ] Clicking each nav item navigates to the correct placeholder page
- [ ] Active nav state highlights correctly
- [ ] Header shows "HORIZON 30" with teal gradient logo mark
- [ ] Dark background (zinc-950) applied to entire app shell
- [ ] No references to salon, pilotage, coiffure, CoCo in remaining frontend code (grep verify)
- [ ] Auth flow still works: login → app shell, logout → login page
- [ ] No console errors in browser dev tools
- [ ] LEARNINGS.md updated if gotchas discovered

## Notes

- The sidebar quick stats panel will show placeholder values ("—") until Sprint 1 wires up real data
- The `(public)/` landing page will still show ComCoi content — retheme it later or just redirect to login for now
- Font loading (Inter + JetBrains Mono) should be added to `app.html` or the layout — see TASK-0.4
- The layout should be responsive: on mobile, sidebar collapses to a bottom tab bar (or defer mobile layout to a later task)
- Keep `frontend/src/lib/api.ts` — the typed API client is reusable, just remove salon-specific endpoint functions
