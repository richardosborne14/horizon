# TASK-2.6: Life Page — Pets Section

**Status:** BACKLOG
**Sprint:** 2
**Priority:** P1 (high)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-2.5

## Context

Simpler than kids — fewer cost events, less interactivity. Reuses `LifeEntityCard` and `CostEventList` from TASK-2.5. The pet-specific header includes a type selector (dog/cat/other) that affects which canned defaults are generated (dogs get toilettage, cats don't; lifespans differ).

**Prototype reference:** `horizon30.jsx` → Life → Pets section. Inline row per pet: name, type select, age, annual cost, remove button.

## Requirements

1. Add pets section to `(app)/life/+page.svelte` below kids section

2. **Pet section** (emerald accent Card, "Animaux 🐾"):
   - For each pet entity: `LifeEntityCard` with:
     - Header fields: name input, type select (Chien/Chat/Autre), birth date input (shows age)
     - CostEventList showing vet/vaccine/food/grooming events
   - AddEntityButton: "+ Ajouter un animal"

3. **Add pet flow:**
   - Dialog/inline: name + type + birth date (or approximate age → derive date)
   - POST with `entity_type: "pet"`, `metadata: {"pet_type": "dog"}`
   - Backend generates type-specific defaults (TASK-2.2)
   - Dog gets: nourriture, véto, vaccins, stérilisation, toilettage, soins vieux
   - Cat gets: nourriture, véto, vaccins, stérilisation, soins vieux (no toilettage)

4. **Type change:** If user changes pet type after creation (dog → cat), offer to regenerate defaults (same pattern as kid birth date change — optional polish)

5. **Age input alternative:** For pets, exact birth date is often unknown. Provide an "approximate age" number input that derives `reference_date = today - (age * 365)`. Toggle between "date exacte" and "âge approximatif".

6. i18n keys under `life.pets.*`

## Technical Approach

### Files to Modify
- `frontend/src/routes/(app)/life/+page.svelte` — add pets section
- `frontend/src/locales/fr.json` — add `life.pets.*` keys

### Pet Header Slot
The `LifeEntityCard` accepts a header slot. For pets:
```svelte
<LifeEntityCard {entity} {onUpdate} {onDelete}>
  <svelte:fragment slot="header">
    <Inp label="Nom" bind:value={entity.name} type="text" />
    <Sel label="Type" bind:value={entity.metadata.pet_type}
      options={[{v:"dog",l:"Chien"},{v:"cat",l:"Chat"},{v:"other",l:"Autre"}]} />
    <Inp label="Âge" value={entity.current_age} suffix="ans" />
  </svelte:fragment>
</LifeEntityCard>
```

## Acceptance Criteria

- [ ] Adding a dog generates dog-specific defaults (includes toilettage)
- [ ] Adding a cat generates cat-specific defaults (no toilettage)
- [ ] Pet age displays correctly
- [ ] Cost events show active/future/past states (old pet → "soins vieux" active)
- [ ] Approximate age input works as alternative to birth date
- [ ] Editing/adding/removing cost events works (reuses CostEventList)
- [ ] Dark theme, prototype layout match
- [ ] i18n keys for all text
- [ ] LEARNINGS.md updated

## Notes

- Pet lifespan is used for the "soins vieux" cost event bracket (lifespan-3 → lifespan). This should be displayed somewhere subtle so the user understands why old-age costs appear.
- Some users will have multiple pets. The section should handle 3-4 pet cards without layout issues.
