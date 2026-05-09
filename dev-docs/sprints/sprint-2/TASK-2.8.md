# TASK-2.8: Life Page — Recurring Expenses + Page Assembly

**Status:** BACKLOG
**Sprint:** 2
**Priority:** P1 (high)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-2.3, TASK-2.5

## Context

The final section on the Life page: time-bounded annual expenses (loan repayments, annual holidays, subscriptions with end dates). Also the page assembly task — ensuring all 5 sections (kids, pets, cars, tech, recurring) render together cohesively with consistent spacing, the intro info box, and sidebar stats wiring.

**Prototype reference:** `horizon30.jsx` → Life → "Dépenses récurrentes à durée limitée" (rose accent). Simple inline rows: description, amount/year, from year, to year, remove button.

## Requirements

### Recurring Expenses Section

1. Add section to `(app)/life/+page.svelte` (rose accent Card, "Dépenses récurrentes à durée limitée 🔄"):

2. Explanatory text: "Remboursements de prêt, colonies de vacances, sport enfant — ce qui revient chaque année mais a une date de fin."

3. Each recurring expense as an inline row:
   - Description text input (flex-1)
   - Annual amount input (€/an, w-24)
   - From year input (w-20)
   - To year input (w-20)
   - Remove button (✕)
   - Auto-save on change (debounce 800ms)

4. "+ Ajouter" dashed button at bottom → creates new row with empty label, amount=0, from=2026, to=2031

5. Load data from `GET /api/recurring-expenses`, save via POST/PUT/DELETE

6. **Hint examples** (placeholder text or subtle suggestion row):
   - "Remboursement prêt auto" · 3 600€/an · 2026→2030
   - "Vacances d'été" · 3 000€/an · 2026→2055
   - "Cours de musique enfant" · 500€/an · 2026→2034

### Page Assembly

7. Verify all 5 sections render in order on the Life page:
   1. Sky info box (intro text about life entities)
   2. Kids (purple accent)
   3. Pets (emerald accent)
   4. Cars (amber accent)
   5. Tech (sky accent)
   6. Recurring (rose accent)

8. Consistent spacing between sections: `space-y-5` (20px gap)

9. **Sidebar stats wiring:** After any add/remove of a kid entity, invalidate the profile summary store (TASK-1.8) so the sidebar "Enfants" count updates.

10. **Empty states:** If a section has no entities, show a subtle message: "Aucun enfant ajouté" with the AddEntityButton. Don't show the section card at all until the user adds their first entity — OR — always show the card with just the add button and a brief explanation. (Decide based on what feels lighter — prototype always shows the card.)

11. **Page load performance:** The page loads ALL life entities in one API call (`GET /api/life-entities`) and recurring expenses in a second call. Two API calls total, not one per section. The `+page.server.ts` groups entities by type for the template.

12. i18n keys under `life.recurring.*` and any missing `life.*` page-level keys

## Technical Approach

### Files to Modify
- `frontend/src/routes/(app)/life/+page.svelte` — add recurring section + verify assembly
- `frontend/src/routes/(app)/life/+page.server.ts` — load recurring expenses alongside entities
- `frontend/src/lib/stores/profile-summary.ts` — invalidate on kid add/remove
- `frontend/src/locales/fr.json` — add `life.recurring.*` keys

### Recurring Expense Row Pattern
```svelte
{#each recurringExpenses as expense}
  <div class="flex items-end gap-2 mb-2">
    <Inp label="Description" bind:value={expense.label} type="text" className="flex-1" />
    <Inp label="€/an" bind:value={expense.annual_amount} className="w-24" />
    <Inp label="De" bind:value={expense.from_year} suffix="" step={1} className="w-20" />
    <Inp label="À" bind:value={expense.to_year} suffix="" step={1} className="w-20" />
    <button on:click={() => remove(expense.id)} class="text-zinc-500 hover:text-rose-400 mb-2">✕</button>
  </div>
{/each}
```

### Data Loading Pattern
```javascript
// +page.server.ts
const [entitiesRes, recurringRes] = await Promise.all([
  fetch(`${API}/life-entities`, { headers }),
  fetch(`${API}/recurring-expenses`, { headers }),
]);

const entities = await entitiesRes.json();
const recurring = await recurringRes.json();

return {
  kids: entities.filter(e => e.entity_type === 'kid' && e.is_active),
  pets: entities.filter(e => e.entity_type === 'pet' && e.is_active),
  cars: entities.filter(e => e.entity_type === 'car' && e.is_active),
  tech: entities.filter(e => e.entity_type === 'tech' && e.is_active),
  recurring,
};
```

## Acceptance Criteria

- [ ] Recurring expenses create, edit, delete correctly
- [ ] From/to year validation: to >= from
- [ ] All 5 sections render on the Life page in correct order with correct accent colors
- [ ] Spacing consistent (space-y-5)
- [ ] Info box renders at top
- [ ] Adding/removing a kid updates sidebar "Enfants" count
- [ ] Page loads with 2 API calls (entities + recurring), not N calls
- [ ] Empty sections show add button with invitation text
- [ ] Sections with entities show entity cards + add button
- [ ] All text via i18n keys
- [ ] Dark theme throughout
- [ ] Smoke test: add 2 kids, 1 dog, 1 car, 1 MacBook, 2 recurring expenses → page renders all correctly → refresh → all data persisted
- [ ] LEARNINGS.md updated

## Notes

- This task is the "integration test" for the Life page. If any of the earlier tasks (2.5, 2.6, 2.7) left rough edges, fix them here.
- The Life page will likely be the longest scrolling page in the app. Consider: should sections be collapsible? For MVP, probably not — the user needs to see everything during initial setup. Collapsible sections are a polish feature.
- The page might feel overwhelming on first visit. The info box at the top sets expectations: "Chaque élément a un cycle de coûts qui évolue avec le temps." After initial setup, users rarely visit this page — they live on the Runway tab (Sprint 4).
