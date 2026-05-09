# TASK-3.5: Projects Frontend — Life Events

**Status:** BACKLOG
**Sprint:** 3
**Priority:** P1 (high)
**Est. effort:** 1 hr
**Dependencies:** TASK-3.2

## Context

Life events are one-time expense spikes — a wedding, a big family trip, a major renovation, moving house. They don't generate income; they're just large costs at a specific year that the projection engine needs to account for. Simple UI: description, year, cost.

**Prototype reference:** `horizon30.jsx` → `Projects` → second Card ("Événements ponctuels 🎉"). Inline rows with description, year, cost, remove button.

## Requirements

1. Add life events section to `(app)/projects/+page.svelte` below investments

2. **Life events card** (amber accent, "Événements de vie ponctuels 🎉"):
   - Intro text: "Mariage, grand voyage, grosse rénovation — dépenses one-shot qui impactent votre trésorerie."
   - For each event project: inline row with:
     - Description text input (flex-1)
     - Year number input (w-24)
     - Cost number input (w-28, €)
     - Remove button (✕)
   - Auto-save on change (debounce 800ms)

3. **Add event button:** "+ Ajouter un événement" → creates event with defaults (label "Événement", year 2030, cost 10 000)

4. Load from `GET /api/projects?type=event`, create via `POST /api/projects/event`

5. **Visual distinction from investments:** No P&L row, no 4-column grid — just a compact inline row. Events are simple by design.

6. i18n keys under `projects.events.*`

## Technical Approach

### Files to Modify
- `frontend/src/routes/(app)/projects/+page.svelte` — add events section
- `frontend/src/locales/fr.json` — add `projects.events.*` keys

### Row Pattern
```svelte
{#each eventProjects as proj}
  <div class="flex items-end gap-3 mb-2">
    <Inp label="Description" bind:value={proj.label} type="text" className="flex-1" />
    <Inp label="Année" bind:value={proj.event_year} suffix="" step={1} className="w-24" />
    <Inp label="Coût" bind:value={proj.event_cost} className="w-28" />
    <button on:click={() => remove(proj.id)} class="text-zinc-500 hover:text-rose-400 mb-2">✕</button>
  </div>
{/each}
```

## Acceptance Criteria

- [ ] Life events create, display, edit, and delete correctly
- [ ] Events show as compact inline rows (not full cards like investments)
- [ ] Year validated (2024-2080 range, from schema)
- [ ] Cost validated (>= 0)
- [ ] Auto-save works
- [ ] Add button creates with defaults
- [ ] Multiple events render cleanly
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] LEARNINGS.md updated

## Notes

- Life events are the simplest entity in the app. Don't over-engineer them.
- Common examples worth showing as placeholder/hint text: "Mariage" (15k), "Tour du monde" (20k), "Rénovation cuisine" (12k), "Déménagement" (5k).
- The projection engine (Sprint 4) applies these as one-time expenses in the specified year. No inflation adjustment needed — the user enters the estimated cost in future euros for that year.
