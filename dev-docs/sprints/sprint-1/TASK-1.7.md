# TASK-1.7: Expenses Frontend Section

**Status:** BACKLOG
**Sprint:** 1
**Priority:** P1 (high)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-1.4, TASK-1.3

## Context

The Expenses section lets users enter their 2026 monthly expenses across 12 categories, then shows an inflation preview table demonstrating how those expenses grow over 5/10/20/30 years under three economic scenarios. The CAF override input is also here. The goal: users enter today's numbers once and understand the long-term impact.

**Prototype reference:** `horizon30.jsx` → `Expenses` component. Stats row, 3-column expense grid, inflation preview table (3 rows × 4 columns), CAF input.

## Requirements

1. Replace placeholder in `frontend/src/routes/(app)/expenses/+page.svelte`

2. **`+page.server.ts`**: Load profile expenses via `GET /api/profile/expenses`, inflation preview via `GET /api/profile/expenses/inflation-preview`, expense labels from API or constants

3. **Stats row** (2 stat cards):
   - Total mensuel (amber) with "base 2026" subtitle
   - Total annuel (amber)

4. **Expense grid card** (amber accent):
   - Intro text: "Saisissez vos dépenses actuelles. L'inflation est appliquée automatiquement dans l'onglet Horizon."
   - 3-column grid of 12 expense inputs
   - Each input: label from EXPENSE_LABELS, number input, €/mois suffix
   - Total updates reactively as inputs change
   - Auto-save entire expense object (debounce 800ms) via `PUT /api/profile/expenses`

5. **Inflation preview card** (rose accent):
   - Table: 3 rows (☀️ Optimiste / ⛅ Modéré / 🌧️ Pessimiste) × 4 columns (+5, +10, +20, +30 ans)
   - Each cell: the user's current monthly total inflated by `cost_living` rate for that scale/horizon
   - Fetched from `GET /api/profile/expenses/inflation-preview`
   - Colour-coded: each row uses the scale's color (emerald/amber/red)
   - Re-fetches when expenses change (debounce, not on every keystroke)

6. **CAF card** (purple accent):
   - Explanatory text: "2+ enfants de moins de 20 ans → allocations. Saisissez votre montant réel ou laissez l'estimation."
   - Monthly CAF override input (number, €/mois)
   - Hint: "Basé sur revenu et nombre d'enfants < 20 ans" 
   - Note: auto-estimation won't work until Sprint 2 (needs kid data). For now the hint says "Saisissez votre montant actuel"
   - Saves to `profile.caf_override_monthly`

7. **i18n keys** under `expenses.*`

## Technical Approach

### Files to Create/Modify
- `frontend/src/routes/(app)/expenses/+page.svelte`
- `frontend/src/routes/(app)/expenses/+page.server.ts`
- `frontend/src/lib/components/InflationPreview.svelte` — reusable table component
- `frontend/src/locales/fr.json` — add `expenses.*` keys
- `frontend/src/locales/en.json` — add `expenses.*` keys

### Inflation Preview Table Pattern
```svelte
{#each Object.entries(scales) as [key, scale]}
  <div class="flex items-center gap-3 p-2 rounded-lg bg-zinc-800/20">
    <span>{scale.emoji}</span>
    <span class="text-xs text-zinc-400 w-20">{scale.label}</span>
    {#each horizons as h}
      <div class="text-center flex-1">
        <p class="text-[9px] text-zinc-500">+{h} ans</p>
        <p class="text-xs font-mono" style="color: {scale.color}">
          {formatCurrency(preview[key][h])}
        </p>
      </div>
    {/each}
  </div>
{/each}
```

## Acceptance Criteria

- [ ] 12 expense inputs render with correct labels
- [ ] Total updates reactively when any input changes
- [ ] Expenses auto-save after 800ms debounce
- [ ] Inflation preview table shows correct values for all 3 scales × 4 horizons
- [ ] Verify math: 2130€/month at 3% for 10 years → 2862€ (moderate)
- [ ] CAF override saves to profile
- [ ] Page survives empty expenses (new user — all zeros)
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] Smoke test: enter loyer=800 → total shows 800 → inflate preview shows 800 growing → refresh → values persisted
- [ ] LEARNINGS.md updated

## Notes

- The inflation preview is the persuasion tool for this section. "Your 2 130€/month becomes 3 840€ in 20 years under pessimistic inflation" — that's the wake-up call that motivates the rest of the app.
- The 3-column grid should be responsive: 2 columns on medium screens, 1 column on mobile.
- Consider grouping: "Logement" (loyer, énergie, impots), "Quotidien" (alimentation, transport, santé), "Lifestyle" (loisirs, abonnements, divers), "Financier" (assurance, crédit). For MVP a flat grid is fine; grouping is a polish task.
