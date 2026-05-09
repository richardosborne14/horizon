# TASK-4.3: Runway — Scale Selector, Goal & Hero Stats

**Status:** BACKLOG
**Sprint:** 4
**Priority:** P0 (critical)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-4.2

## Context

The top section of the Runway page — the controls and headline numbers. The scale selector toggles between three economic scenarios, the goal input sets the monthly income target, and the hero stat cards show the two numbers that matter most: total wealth at retirement and monthly passive income.

This task also sets up the page's data-fetching pattern that all subsequent Runway tasks will use.

**Prototype reference:** `horizon30.jsx` → `Runway` component → top section. 3-button scale selector, goal input card, 2 large stat cards.

## Requirements

1. Replace placeholder in `frontend/src/routes/(app)/runway/+page.svelte`

2. **`+page.server.ts`**: Load projection via `GET /api/projection?scale={profile.world_scale}` and profile (for goal value and birth date)

3. **Scale selector** — 3-button bar at the top:
   - ☀️ Optimiste / ⛅ Modéré / 🌧️ Pessimiste
   - Selected button: `border-zinc-600 bg-zinc-800 text-white`
   - Unselected: `border-zinc-800/40 bg-zinc-900/30 text-zinc-500`
   - Clicking a scale: re-fetches projection via client-side `fetch(/api/projection?scale=X)`, also saves to profile (`PUT /api/profile {world_scale: X}`)
   - Loading state while re-fetching (subtle opacity reduction, not a spinner)

4. **Goal input card** (teal accent, "Objectif de revenu mensuel à la retraite 🎯"):
   - Explanatory text: "Combien voulez-vous toucher (travail + passif + projets) pour ne plus dépendre de personne ?"
   - Number input for `monthly_revenue_goal` (auto-saves to profile)
   - Dynamic hint below input:
     - If goal reached: `"✓ Atteint en {year} (à {age} ans)"` in teal
     - If not reached: `"Pas encore atteint — augmentez l'épargne ou ajoutez des projets"` in amber
     - If no goal set: empty

5. **Hero stat cards** (2 cards, side by side):
   - Left: `"Patrimoine à {targetAge} ans ({year})"` → `fmtK(final_wealth)` in teal
   - Right: `"Revenu passif mensuel"` → `fmt(final_passive_monthly)` with sub "Règle des 4%" in emerald

6. **Reactive data store**: Create a `projectionData` Svelte store that holds the current timeline + summary. Scale changes and goal saves trigger a re-fetch that updates this store. All subsequent components (charts, milestones, table, insights) subscribe to this store.

7. i18n keys under `runway.*`

## Technical Approach

### Files to Create/Modify
- `frontend/src/routes/(app)/runway/+page.svelte`
- `frontend/src/routes/(app)/runway/+page.server.ts`
- `frontend/src/lib/stores/projection.ts` — reactive projection store
- `frontend/src/lib/components/runway/ScaleSelector.svelte`
- `frontend/src/lib/components/runway/GoalInput.svelte`
- `frontend/src/locales/fr.json` — add `runway.*` keys

### Reactive Re-fetch Pattern
```svelte
<script>
  import { projectionStore } from '$lib/stores/projection';
  
  let scale = data.profile.world_scale || 'moderate';
  
  async function changeScale(newScale) {
    scale = newScale;
    const res = await fetch(`/api/projection?scale=${newScale}`);
    $projectionStore = await res.json();
    // Also persist the preference
    await fetch('/api/profile', { method: 'PUT', body: JSON.stringify({ world_scale: newScale }) });
  }
</script>
```

## Acceptance Criteria

- [ ] Scale selector renders 3 buttons with correct labels and emojis
- [ ] Clicking a scale re-fetches projection and updates all displayed data
- [ ] Goal input saves to profile and shows dynamic hint
- [ ] Goal hint shows correct year when achieved
- [ ] Hero stats display final wealth and passive income from projection
- [ ] Loading state visible during re-fetch (not jarring)
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] Smoke test: set goal to 4000 → shows "Atteint en 20XX" or "Pas encore atteint" → switch to pessimistic → numbers change → switch back → numbers restore
- [ ] LEARNINGS.md updated

## Notes

- The scale selector is the most-used control on this page. Make the transition smooth — the numbers should update without a full page flash.
- The projection store pattern is important to get right here because 4.4, 4.5, and 4.6 all consume it. Don't load projection data in each component — load once, share via store.
- If the user hasn't set a birth_date yet, the projection API returns a 422. Handle this gracefully: show a message "Renseignez votre date de naissance dans Identité pour voir votre projection" with a link to the Identity section.
