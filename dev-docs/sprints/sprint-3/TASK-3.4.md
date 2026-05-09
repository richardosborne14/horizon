# TASK-3.4: Projects Frontend — Investments

**Status:** BACKLOG
**Sprint:** 3
**Priority:** P1 (high)
**Est. effort:** 2 hr
**Dependencies:** TASK-3.2

## Context

Investment projects are the "active wealth building" play — buying a gîte, a rental apartment, starting a side business. Each project has a mini P&L showing the user exactly what they'll earn after costs and tax. This is where the app goes beyond passive savings and into "here's how you build real assets."

**Prototype reference:** `horizon30.jsx` → `Projects` → first Card ("Investissements 🏡"). Each project is a bordered sub-card with name, year, 4 financial inputs, and a computed P&L summary row.

## Requirements

1. Create `frontend/src/routes/(app)/projects/+page.svelte` — the Projects section page.

2. **`+page.server.ts`**: Load projects via `GET /api/projects`

3. **Investment projects card** (emerald accent, "Investissements 🏡"):
   - Intro text: "Immobilier locatif, gîte — chaque projet a son mini bilan : revenus, charges, fiscalité."
   - For each investment project, a bordered sub-card:

     **Header row:**
     - Name input (text, flex-1)
     - Start year input (number)
     - Delete button (✕ with confirmation)

     **4-column input grid:**
     - Coût d'achat (purchase_cost)
     - Revenus locatifs/an (annual_income)
     - Charges annuelles/an (annual_expenses) — hint: "Ménage, entretien, assurance, travaux"
     - Taux d'imposition (tax_rate as %) — hint: "30% micro-foncier, variable en réel"

     **P&L summary row** (subtle bg, inline stats):
     - `Brut/an: {fmt(pnl.gross_annual)}€`
     - `Net après impôt: {fmt(pnl.net_annual)}€` (emerald if positive, rose if negative)
     - `Rendement: {fmtPct(pnl.yield_pct)}` (teal)

   - Auto-save on input change (debounce 800ms), P&L recomputes from API response

4. **Add investment button:** dashed "+ Ajouter un investissement" → creates project with sensible defaults (label "Nouveau projet", start 2035, cost 80 000, income 8 000, expenses 2 500, tax 30%)

5. **P&L display logic:**
   - P&L comes from the API (computed server-side in TASK-3.2)
   - After each save, the updated project with fresh P&L is returned
   - If gross is negative (expenses > income), show in rose with a note: "Ce projet coûte plus qu'il ne rapporte"
   - Yield only shown if purchase_cost > 0

6. i18n keys under `projects.invest.*`

## Technical Approach

### Files to Create/Modify
- `frontend/src/routes/(app)/projects/+page.svelte` — investments section (events + status change added in 3.5/3.6)
- `frontend/src/routes/(app)/projects/+page.server.ts`
- `frontend/src/lib/components/InvestmentProjectCard.svelte`
- `frontend/src/locales/fr.json` — add `projects.invest.*` keys

### P&L Summary Row Pattern
```svelte
<div class="mt-3 p-2 rounded bg-zinc-800/30 flex gap-4 text-xs">
  <span class="text-zinc-400">Brut:
    <strong class="text-zinc-200">{fmt(project.pnl.gross_annual)}</strong>/an
  </span>
  <span class="text-zinc-400">Net:
    <strong class={project.pnl.net_annual >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
      {fmt(project.pnl.net_annual)}
    </strong>/an
  </span>
  <span class="text-zinc-400">Rendement:
    <strong class="text-teal-400">
      {project.pnl.yield_pct != null ? fmtPct(project.pnl.yield_pct) : '—'}
    </strong>
  </span>
</div>
```

## Acceptance Criteria

- [ ] Investment projects load from API with P&L computed
- [ ] Editing any input saves and returns updated P&L
- [ ] P&L math displayed correctly (verify: 80k/8k/2.5k/30% → net 3 850€, yield 4.81%)
- [ ] Negative P&L shown in rose with warning text
- [ ] Add button creates project with defaults
- [ ] Delete soft-removes with confirmation
- [ ] Multiple projects render without layout issues
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] Sidebar "Projets" count updates on add/remove
- [ ] LEARNINGS.md updated

## Notes

- The P&L is the key "aha" for this section. Users often overestimate rental yields because they forget about tax, cleaning costs, insurance, vacancy periods, and maintenance. Showing the real net return is sobering and valuable.
- Future enhancement: add an "occupancy rate" field (default 80%) that reduces annual_income. For MVP, the user just enters their conservative income estimate.
- The projection engine (Sprint 4) will grow the income at ~2%/year and inflate expenses. The P&L on this page is a static Year 1 snapshot — useful for comparison but not the full picture.
