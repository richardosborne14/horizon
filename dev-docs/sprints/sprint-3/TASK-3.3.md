# TASK-3.3: Savings Frontend Section

**Status:** BACKLOG
**Sprint:** 3
**Priority:** P0 (critical)
**Est. effort:** 2 hr
**Dependencies:** TASK-3.1

## Context

The Épargne section shows all 7 investment vehicles with their specs, the user's existing balances, and monthly contribution allocations. It's the "where does my money go to grow" configuration screen. The user sees each vehicle's rate, tax treatment, ceiling, and risk level alongside their allocation inputs.

**Prototype reference:** `horizon30.jsx` → `Savings` component. Stats row (existing total, monthly total, annual total), then a list of vehicle cards each with balance + monthly contribution inputs.

## Requirements

1. Replace placeholder in `frontend/src/routes/(app)/savings/+page.svelte`

2. **`+page.server.ts`**: Load allocations via `GET /api/investments` (returns all 7 vehicles with user data + vehicle specs)

3. **Stats row** (3 stat cards):
   - Épargne existante (purple) — sum of all existing_balance
   - Versement mensuel (teal) — sum of all monthly_contribution
   - Versement annuel (teal) — monthly × 12

4. **Vehicle list card** (purple accent, "Épargne & allocation mensuelle ◆"):
   - For each of the 7 vehicles, a bordered sub-card containing:
     - **Header row:** colored dot (vehicle color) + label + spec summary in mono text:
       `"2,5%/an • net d'impôt • plafond 22 950€"` or `"7,0%/an • 17,2% PFU • plafond 150 000€"`
     - **Two inputs side by side:** "Solde actuel" (existing_balance) + "Versement mensuel" (monthly_contribution)
     - Ceiling warning: if balance > ceiling, show subtle amber text: `"⚠️ Dépasse le plafond de {ceiling}€"`

5. **Vehicle ordering:** Match prototype: Livret A → LDDS → AV euro → AV UC → PEA → SCPI → PER (safe → risky → retirement-locked)

6. **Auto-save pattern:** Each vehicle saves independently on input change (debounce 800ms, `PUT /api/investments/{vehicle_key}`). Stats row updates reactively.

7. **Disposable income reference** (optional enhancement): If Sprint 1 data is available, show at the top: "Votre disponible mensuel (après cotisations et charges) : {fmt(disposable)}€". Calculated as `monthlyGross - monthlyCharges - totalExpenses`. Helps the user know how much they CAN allocate. Show amber warning if total allocations exceed disposable.

8. i18n keys under `savings.*`

## Technical Approach

### Files to Create/Modify
- `frontend/src/routes/(app)/savings/+page.svelte`
- `frontend/src/routes/(app)/savings/+page.server.ts`
- `frontend/src/lib/components/VehicleCard.svelte` — reusable per-vehicle card
- `frontend/src/locales/fr.json` — add `savings.*` keys

### Vehicle Card Pattern (from prototype)
```svelte
{#each vehicles as v}
  <div class="border border-zinc-800/30 rounded-lg p-3 mb-3">
    <div class="flex items-center gap-2 mb-2">
      <div class="w-2.5 h-2.5 rounded-full" style="background-color: {v.spec.color}" />
      <span class="text-xs font-semibold text-zinc-200">{v.spec.label}</span>
      <span class="text-[10px] text-zinc-500 font-mono ml-auto">
        {fmtPct(v.spec.rate)}/an
        {v.spec.tax_free ? '• net' : `• ${fmtPct(v.spec.tax_rate)} PFU`}
        {#if v.spec.ceiling}• plafond {fmtK(v.spec.ceiling)}{/if}
      </span>
    </div>
    <div class="flex gap-3">
      <Inp label="Solde actuel" bind:value={v.existing_balance} />
      <Inp label="Versement mensuel" bind:value={v.monthly_contribution} />
    </div>
    {#if v.spec.ceiling && v.existing_balance > v.spec.ceiling}
      <p class="text-[10px] text-amber-400 mt-1">⚠️ Dépasse le plafond</p>
    {/if}
  </div>
{/each}
```

## Acceptance Criteria

- [ ] All 7 vehicles displayed in correct order with specs
- [ ] Existing balances and monthly contributions load from API
- [ ] Editing a value saves to backend (debounce 800ms)
- [ ] Stats row totals update reactively
- [ ] Ceiling warning shows when balance > ceiling (Livret A > 22 950)
- [ ] Vehicle colors match prototype
- [ ] Spec summary line shows rate, tax treatment, ceiling, risk
- [ ] Sidebar "Épargne/m" updates when contributions change
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] Smoke test: set Livret A balance=5000, monthly=200; PEA monthly=300 → stats show 5000 existing, 500/month, 6000/year → refresh → persisted
- [ ] LEARNINGS.md updated

## Notes

- The vehicle descriptions (from VEHICLE_SPECS) are deliberately brief — they're reference info, not financial advice. The disclaimer at the bottom of the Runway page covers the "not financial advice" caveat.
- PER's `tax_deductible: True` should show as a distinct feature: "Versements déductibles de l'IR" in the spec line. This is a selling point for PER vs other vehicles.
- The "disposable income reference" enhancement is nice-to-have. It requires reading profile + expenses data that's outside this page's direct scope. If it adds complexity, skip it and let the user figure out their budget from the Expenses page.
