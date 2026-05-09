# TASK-2.5: Life Page — Kids Section

**Status:** BACKLOG
**Sprint:** 2
**Priority:** P0 (critical)
**Est. effort:** 2.5 hr
**Dependencies:** TASK-2.1, TASK-2.2

## Context

The most complex life entity UI. Each kid is an expandable card showing their cost events as an editable list with visual indicators for active (happening now), future (will happen), and past (no longer relevant) events. This task also creates the **reusable components** (LifeEntityCard, CostEventList, AddEntityButton) that TASK-2.6 and TASK-2.7 will reuse.

**Prototype reference:** `horizon30.jsx` → `Life` component → Kids section. Each kid is a bordered card with name + age inputs at top, cost event list below with purple/grey/faded dot indicators, inline amount editing, and an "add custom expense" button.

## Requirements

1. **Create `(app)/life/+page.svelte`** — the Life section page shell. For this task, only the kids section is wired; pets/cars/tech are placeholders.

2. **Create `+page.server.ts`**: Load life entities via `GET /api/life-entities`, grouped by type.

3. **Create reusable components** in `frontend/src/lib/components/life/`:

   **`LifeEntityCard.svelte`:**
   - Props: `entity`, `onUpdate`, `onDelete`, `headerSlot` (for type-specific header fields)
   - Bordered card with entity name + age display
   - Contains a CostEventList
   - Delete button with confirmation modal
   - Auto-saves entity on any change (debounce 800ms)

   **`CostEventList.svelte`:**
   - Props: `events`, `entityAge`, `onEventsChange`
   - Renders each cost event as a row:
     - Dot indicator: purple if `entityAge >= from_age && entityAge <= to_age` (active), grey if future, faded/dimmed if past
     - Editable label (text input, transparent bg)
     - Age range display: `"0→3 ans"` (read-only for canned, editable for user-created)
     - Amount input (number, right-aligned)
     - Frequency label: `"€/mois"` or `"€/an"` or `"une fois"`
   - "Add custom expense" button at bottom → adds new event with `source: "user"`
   - Events sorted: active first, then future, then past

   **`AddEntityButton.svelte`:**
   - Dashed border button: "+ Ajouter un enfant"
   - On click: opens a minimal form (name + birth date) → POST to API → entity created with canned defaults → card appears

4. **Kids section implementation:**
   - Sky info box at top: "Entités de vie. Enfants, animaux, voitures, tech — chaque élément a un cycle de coûts..."
   - Purple-accent Card title: "Enfants 👶"
   - For each kid entity: `LifeEntityCard` with:
     - Header: name input + birth date input (shows computed age as "X ans")
     - Cost event list with active/future/past indicators
   - AddEntityButton at bottom

5. **Add kid flow:**
   - User clicks "+ Ajouter un enfant"
   - Minimal dialog/inline form: name + birth date
   - POST `/api/life-entities` with `entity_type: "kid"`, empty `cost_events`
   - Backend populates canned defaults (TASK-2.2) including September rule
   - Card appears immediately with pre-populated events
   - User can then adjust amounts, add custom events, remove unwanted canned events

6. **Editing flow:**
   - Changing an amount: inline number input → debounce → PUT full entity with updated cost_events
   - Adding custom event: append to events array with `source: "user"`, save
   - Removing event: filter from array, save (don't delete canned events permanently — set `is_active: false` on the event)
   - Changing name or birth date: save, if birth date changed and events are all `source: "default"`, offer to regenerate defaults (toast: "Date de naissance modifiée. Recalculer les dépenses automatiques ?")

7. **i18n keys** under `life.kids.*`

## Technical Approach

### Files to Create
- `frontend/src/routes/(app)/life/+page.svelte`
- `frontend/src/routes/(app)/life/+page.server.ts`
- `frontend/src/lib/components/life/LifeEntityCard.svelte`
- `frontend/src/lib/components/life/CostEventList.svelte`
- `frontend/src/lib/components/life/AddEntityButton.svelte`
- `frontend/src/locales/fr.json` — add `life.*` keys
- `frontend/src/locales/en.json` — add `life.*` keys

### CostEventList Row Pattern (from prototype)
```svelte
{#each sortedEvents as event}
  <div class="flex items-center gap-2 text-xs p-2 rounded {stateClass(event, entityAge)}">
    <span class="w-1.5 h-1.5 rounded-full {dotColor(event, entityAge)}" />
    <input type="text" value={event.label}
      class="flex-1 bg-transparent text-zinc-300 text-xs focus:outline-none"
      on:blur={() => save()} />
    <span class="text-zinc-500 text-[10px] font-mono">{event.from_age}→{event.to_age} ans</span>
    <input type="number" value={event.amount}
      class="w-16 bg-zinc-800/40 border border-zinc-700/30 rounded px-1.5 py-0.5 text-xs font-mono text-right"
      on:blur={() => save()} />
    <span class="text-[10px] text-zinc-500">{freqLabel(event.frequency)}</span>
  </div>
{/each}
```

### State Logic
```javascript
function getEventState(event, entityAge) {
  if (entityAge > event.to_age) return 'past';     // greyed out, opacity-30
  if (entityAge >= event.from_age) return 'active'; // purple bg tint, purple dot
  return 'future';                                   // normal, grey dot
}
```

## Acceptance Criteria

- [ ] "Add kid" creates entity with canned defaults populated
- [ ] September rule reflected: kid born March 2025 → crèche ends at age 3; kid born Oct 2025 → crèche ends at age 4
- [ ] Cost events display with correct active/future/past visual states
- [ ] Editing an amount saves to backend
- [ ] Adding a custom expense appears in the list with `source: "user"`
- [ ] Removing a kid shows confirmation, then soft-deletes
- [ ] Changing birth date offers to regenerate defaults
- [ ] LifeEntityCard and CostEventList are generic (not kid-specific)
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] Smoke test: add kid born today → all events are "future" except crèche (active); add kid born 2015 → school events active, crèche past
- [ ] LEARNINGS.md updated

## Notes

- The CostEventList is the most interactive component in the app. Get the save/debounce pattern right here — every other entity section reuses it.
- The "regenerate defaults" flow on birth date change is optional polish — if it adds too much complexity, skip it for MVP and just let the user manually adjust events.
- Consider: when the user removes a canned event, should it disappear entirely or show as "disabled"? For MVP, just remove it from the array. The AI suggestions feature (Sprint 5) can later suggest re-adding removed canned events.
