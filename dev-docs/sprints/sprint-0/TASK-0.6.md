# TASK-0.6: Prototype Reference Doc

**Status:** DONE ✅ (2026-05-08)
**Sprint:** 0
**Priority:** P2 (medium)
**Est. effort:** 30 min
**Dependencies:** None

## Context

The Horizon 30 interactive prototype (`horizon30.jsx`) was built during the brainstorming phase and validated with the project owner. It serves as the UX source of truth for all frontend work. This task commits the prototype to the repo and creates a reference document that maps prototype sections to planned routes, components, and design patterns.

This should be done early in Sprint 0 so that TASK-0.3 (frontend strip) and TASK-0.4 (dark theme) can reference it.

## Requirements

1. **Create directory** `dev-docs/prototype/`

2. **Copy prototype file** to `dev-docs/prototype/horizon30.jsx`

3. **Create `dev-docs/PROTOTYPE_REFERENCE.md`** with the following sections:

### Section Mapping

| Prototype Section | Route | Key Components | Sprint |
|---|---|---|---|
| Identity | `(app)/identity/` | ProfileForm, RateSchedulePreview | 1 |
| Revenue | `(app)/revenue/` | GrossInput, GrowthPresets, TaxBreaks, CA5YearPreview | 1 |
| Expenses | `(app)/expenses/` | ExpenseGrid, InflationPreview, CAFInput | 1 |
| Life | `(app)/life/` | KidCard, PetCard, CarCard, TechCard, RecurringList | 2 |
| Savings | `(app)/savings/` | VehicleCard (×7), AllocationSliders | 3 |
| Projects | `(app)/projects/` | InvestmentPNL, LifeEventRow, StatusChangeSimulator | 3 |
| Runway | `(app)/runway/` | ScaleSelector, GoalInput, WealthChart, IncomeChart, MilestoneTimeline, ProjectionTable, InsightCards | 4 |

### Design Patterns (from prototype)

Document each of these with a brief description and where they appear:

- **Card component**: `border border-zinc-800/60 rounded-xl bg-zinc-900/40` with optional `border-l-2` accent. Used everywhere.
- **Stat card**: 9px uppercase label, lg mono bold value, 10px subtitle. Used in stats rows.
- **Input component**: dark bg, zinc border, teal focus ring, label above, suffix inside, hint below.
- **Scale selector**: 3-button bar (☀️ Optimiste / ⛅ Modéré / 🌧️ Pessimiste). Used in Expenses preview and Runway.
- **Growth presets**: 4-card grid with label, rate, description. Revenue section.
- **Life entity cost events**: list with active/future/past dot indicators (purple/grey/faded). Life section kids.
- **Chart**: SVG area chart with gradient fill. No chart library. Used in Runway.
- **Milestone timeline**: vertical line with colored dots and labels. Runway section.
- **Info box**: colored bg/border (teal, purple, amber) with 💡/🎯/⚠️ icon. Contextual tips.

### Color Semantics

| Color | Token | Usage |
|-------|-------|-------|
| Teal | `teal-400` (#2dd4bf) | Primary accent, active nav, CTAs, positive net, wealth chart |
| Emerald | `emerald-400` (#34d399) | Growth, passive income, goal reached |
| Amber | `amber-400` (#fbbf24) | Warnings, cotisation rates, cost-of-living, goal line |
| Rose | `rose-400` (#fb7185) | Negative values, errors, charges |
| Purple | `purple-400` (#a78bfa) | Savings, kids, investments, CAF |
| Sky | `sky-400` (#38bdf8) | Tech, information, life entities intro |

### Typography

| Element | Font | Weight | Size | Color |
|---------|------|--------|------|-------|
| Section label (card header) | Inter | 600 (semibold) | 12px (xs) | zinc-300 |
| Input label | Inter | 600 | 10px | zinc-400 |
| Stat value | JetBrains Mono | 700 (bold) | 18px (lg) | accent color |
| Stat label | Inter | 400 | 9px | zinc-500 |
| Table data | JetBrains Mono | 400-600 | 11px | varies |
| Hint text | Inter | 400 | 10px | zinc-500 |
| Nav item | Inter | 500 | 12px (xs) | zinc-500 / white |

## Technical Approach

### Files to Create
- `dev-docs/prototype/horizon30.jsx` — the prototype file
- `dev-docs/PROTOTYPE_REFERENCE.md` — the reference document

## Acceptance Criteria

- [ ] Prototype file committed at `dev-docs/prototype/horizon30.jsx`
- [ ] Reference doc created with all sections above
- [ ] Section mapping table complete (7 sections → routes + components + sprint)
- [ ] Design patterns section covers all reusable patterns from prototype
- [ ] Color semantics table complete
- [ ] Typography table complete
- [ ] Document is referenced in `.clinerules` "Before EVERY Task" section

## Notes

- The prototype is React/JSX — the actual app is SvelteKit. The prototype is a UX reference, not code to be ported. Component names and patterns translate, but syntax does not.
- The prototype uses Tailwind utility classes directly. The Svelte components should do the same, with CSS custom properties only for semantic tokens (see TASK-0.4).
- This document will be updated as Sprint 1-4 tasks flesh out the components. It's a living reference, not a frozen spec.
