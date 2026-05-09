# TASK-1.6: Revenue Frontend Section

**Status:** BACKLOG
**Sprint:** 1
**Priority:** P1 (high)
**Est. effort:** 2 hr
**Dependencies:** TASK-1.1, TASK-1.2, TASK-1.3

## Context

The Revenue section shows gross CA, cotisation breakdown, growth expectations, and tax break inputs. The key UX innovation vs a simple form is the **growth preset selector** — 4 cards with descriptions explaining what each growth rate means in practice, plus a 5-year CA preview so the user sees the impact immediately. CESU and charity tax credits are calculated live.

**Prototype reference:** `horizon30.jsx` → `Revenue` component. Stats row (3 cards), CA input, 4-card growth grid, 5-year preview row, CESU/charity inputs with purple info box.

## Requirements

1. Replace placeholder in `frontend/src/routes/(app)/revenue/+page.svelte`

2. **`+page.server.ts`**: Load profile + growth presets (`GET /api/constants/growth-presets`) + AE rate for current year

3. **Stats row** (3 stat cards):
   - CA brut mensuel (teal)
   - Cotisations mensuelles (rose) with rate as subtitle
   - Net après cotisations (emerald)
   - All computed from `profile.monthly_gross_ca` × `get_ae_rate(type, 2026)` — computation happens on server, returned in page data

4. **CA input card** (teal accent):
   - Single number input for `monthly_gross_ca`
   - Auto-save, stats row reacts immediately

5. **Growth preset card** (emerald accent):
   - Explanatory paragraph: "Comment votre CA va évoluer ?"
   - 4-card grid fetched from `/api/constants/growth-presets`
   - Each card: label, rate (bold mono), description
   - Selected card highlighted (teal border + bg)
   - Clicking a preset saves `growth_preset` to profile
   - "Personnalisé" card shows an inline number input for custom rate
   - **5-year CA preview**: row of 5 boxes (2026→2030) showing projected monthly CA. Computed client-side: `ca * (1 + rate)^y`. Updates reactively when CA or preset changes.

6. **Tax breaks card** (purple accent):
   - CESU annual input with live credit display: `"Crédit d'impôt 50% → économie {fmt(min(cesu*0.5, 6000))}€/an"`
   - Charity annual input with live credit display: `"Réduction 66% → économie {fmt(min(charity*0.66, 20000))}€/an"`
   - Purple info box explaining CESU (from prototype)
   - Both auto-save to profile

7. **i18n keys** under `revenue.*`

## Technical Approach

### Files to Create/Modify
- `frontend/src/routes/(app)/revenue/+page.svelte`
- `frontend/src/routes/(app)/revenue/+page.server.ts`
- `frontend/src/lib/components/StatCard.svelte` — reusable (if not created in 1.5)
- `frontend/src/lib/components/GrowthPresetGrid.svelte`
- `frontend/src/locales/fr.json` — add `revenue.*` keys
- `frontend/src/locales/en.json` — add `revenue.*` keys

### Client-Side Computation Exception
The 5-year CA preview and CESU/charity credit displays are computed client-side for instant reactivity. This is display-only preview math — the authoritative projection runs server-side in Sprint 4. Acceptable because: the formulas are trivial (`ca * (1 + r)^y` and `min(x * 0.5, 6000)`), and waiting for an API roundtrip on every keystroke would kill the UX.

## Acceptance Criteria

- [ ] Stats row shows correct CA, cotisations, and net for the user's current profile
- [ ] Changing CA input updates stats row reactively
- [ ] Growth presets render from API data with correct descriptions
- [ ] Selecting a preset highlights it and saves to profile
- [ ] "Personnalisé" shows custom rate input
- [ ] 5-year preview updates when CA or growth rate changes
- [ ] CESU credit calculation correct: `min(cesu * 0.5, 6000)`
- [ ] Charity credit calculation correct: `min(charity * 0.66, 20000)`
- [ ] All inputs auto-save (debounce 800ms)
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] Smoke test: set CA to 5000, select "Ambitieux" → 5-year preview shows ~5000, 5300, 5618, 5955, 6312
- [ ] LEARNINGS.md updated

## Notes

- The stats row computation (CA × rate = cotisations) should come from the server via page data, not computed client-side, because the rate lookup requires the AE rate engine. The `+page.server.ts` computes and passes `{ grossMonthly, cotisationsMonthly, netMonthly, aeRate }` to the page.
- The 5-year preview is the "aha moment" for this section — it makes abstract percentages tangible. "Oh, 3% growth means my 5000€ becomes 5796€ in 5 years." Worth spending time making it look good.
