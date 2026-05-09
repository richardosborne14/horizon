# TASK-4.6: Runway — Insights & Page Assembly

**Status:** BACKLOG
**Sprint:** 4
**Priority:** P1 (high)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-4.3, TASK-4.4, TASK-4.5

## Context

The bottom of the Runway page: contextual insight cards that tell the user whether they're on track, and what levers they can pull if not. Plus the legal disclaimer. This task also assembles all Runway components into the final page layout and verifies everything works together.

**Prototype reference:** `horizon30.jsx` → `Runway` → bottom section. Green card for goal reached, amber card for gap, grey disclaimer.

## Requirements

### Insight Cards

1. Create `frontend/src/lib/components/runway/InsightCards.svelte`:

   **Goal reached** (shown when `summary.goal_year` exists AND `final_passive_monthly >= goal`):
   ```
   🏆 Objectif atteint.
   À {targetAge} ans, vos revenus passifs ({fmt(passive)}/mois) couvrent votre objectif.
   Vous n'avez pas besoin de la retraite d'État.
   ```
   Style: `bg-emerald-950/15 border border-emerald-900/30 rounded-xl p-4`, text `text-emerald-300`

   **Gap to close** (shown when goal is set but `final_passive_monthly < goal`):
   ```
   ⚠️ Gap à combler.
   Vos revenus passifs projetés ({fmt(passive)}/mois) sont en dessous de votre objectif ({fmt(goal)}).
   Pistes : augmenter l'épargne mensuelle, ajouter un projet immobilier, ou changer de statut juridique.
   ```
   Style: `bg-amber-950/15 border border-amber-900/30`, text `text-amber-300`

   **No goal set** (shown when `monthly_revenue_goal` is null or 0):
   ```
   💡 Définissez un objectif.
   Sans objectif, la projection montre l'évolution mais pas la destination. Combien voulez-vous
   toucher par mois à la retraite ? Renseignez-le ci-dessus.
   ```
   Style: `bg-teal-950/10 border border-teal-900/20`, text `text-teal-300/70`

   **Disclaimer** (always shown, last card):
   ```
   ⚖️ Simulateur uniquement. Ne constitue pas un conseil financier, fiscal ou juridique.
   Rendements historiques moyens, cotisations projetées sur tendances législatives.
   Les rendements passés ne préjugent pas des rendements futurs.
   ```
   Style: `bg-zinc-900/40 border border-zinc-800/40`, text `text-zinc-500 text-[10px]`

2. Insights react to the projection store — changing scale may flip from "goal reached" to "gap."

### Page Assembly

3. Verify the full Runway page renders all components in order:
   1. Scale selector (3 buttons)
   2. Goal input card
   3. Hero stat cards (2 side by side)
   4. Wealth chart card
   5. Income chart card (with goal line)
   6. Milestones card (if any)
   7. Projection table card
   8. Insight cards
   9. Disclaimer

4. Spacing: `space-y-5` between all sections

5. **Page-level error states:**
   - No birth_date → full-page message: "Pour voir votre horizon, renseignez votre date de naissance dans la section Identité." Link to `/identity`.
   - No monthly_gross → similar message pointing to Revenue section
   - Projection API error → error card with retry button

6. **Loading state:** On initial load and scale change, the page content (below scale selector) reduces opacity to 50% while the projection re-fetches. No spinner, no skeleton — just a subtle fade.

7. i18n keys under `runway.insights.*` and `runway.errors.*`

### Integration Verification

8. Full smoke test scenario:
   - Profile: age 40, target 70, BNC, 5000€/month, moderate growth
   - Expenses: 2130€/month total
   - Kids: 2 (ages 10, 1)
   - Car: petrol, age 5, cycle 8
   - Savings: Livret A 200, PEA 200, AV 200, PER 100 = 700/month
   - Project: gîte in 2035 (80k cost, 8k income, 2.5k expenses, 30% tax)
   - Goal: 4000€/month
   - Expected: wealth trajectory rises, kid expenses visible then tapering, gîte income appears 2036, milestones appear, goal line on income chart, table shows data every 5 years

## Technical Approach

### Files to Create/Modify
- `frontend/src/lib/components/runway/InsightCards.svelte`
- `frontend/src/routes/(app)/runway/+page.svelte` — final assembly
- `frontend/src/locales/fr.json` — add `runway.insights.*`, `runway.errors.*` keys

### Error State Pattern
```svelte
{#if !profile.birth_date}
  <div class="text-center py-20">
    <p class="text-lg text-zinc-400 mb-2">📅 Date de naissance requise</p>
    <p class="text-sm text-zinc-500 mb-4">Pour calculer votre horizon, renseignez votre date de naissance.</p>
    <a href="/identity" class="text-teal-400 hover:text-teal-300 text-sm underline">
      Aller à Identité →
    </a>
  </div>
{:else if projectionError}
  <div class="text-center py-20">
    <p class="text-lg text-zinc-400 mb-2">Erreur de calcul</p>
    <button on:click={retry} class="text-teal-400 hover:text-teal-300 text-sm underline">Réessayer</button>
  </div>
{:else}
  <!-- Full runway content -->
{/if}
```

## Acceptance Criteria

- [ ] Goal reached → green insight card with correct numbers
- [ ] Gap to close → amber insight card with actionable suggestions
- [ ] No goal → teal nudge card
- [ ] Disclaimer always shown
- [ ] Insights update when scale changes (goal may become unreachable under pessimistic)
- [ ] All 9 sections render in correct order on the page
- [ ] No birth_date → helpful error with link to Identity
- [ ] Loading state: subtle opacity fade during re-fetch
- [ ] Full smoke test passes (scenario above)
- [ ] All text via i18n keys
- [ ] Dark theme consistent throughout
- [ ] Page scrolls smoothly (no layout jumps during re-render)
- [ ] LEARNINGS.md updated

## Notes

- The insight cards are the "so what" of the projection. Without them, the user sees charts and numbers but may not know if they're good or bad. The insight text gives a clear verdict and actionable next steps.
- The "gap to close" suggestions should be specific: "augmenter l'épargne mensuelle" (go to Savings), "ajouter un projet immobilier" (go to Projects), "changer de statut" (go to Projects > Status Change). Consider making these clickable links.
- The disclaimer is legally important. It must always be visible and cannot be dismissed.
