# TASK-2.7: Life Page — Cars & Tech Sections

**Status:** BACKLOG
**Sprint:** 2
**Priority:** P1 (high)
**Est. effort:** 2 hr
**Dependencies:** TASK-2.5

## Context

Cars and tech share a "depreciating asset with replacement cycle" pattern. Both have running costs, periodic replacement events, and type-specific variations. Cars add CT inspections and fuel-type cost differences. Tech adds device-type variations. Both reuse the LifeEntityCard and CostEventList from TASK-2.5.

**Prototype reference:** `horizon30.jsx` → Life → Cars section (amber accent) and Tech section (sky accent). Both show inline rows with type-specific fields.

## Requirements

### Cars Section (amber accent Card, "Véhicules 🚗")

1. For each car entity: `LifeEntityCard` with header:
   - Name input ("Voiture principale")
   - Fuel type select: Essence / Diesel / Électrique / Hybride
   - Acquisition date or approximate age
   - Replacement cycle input (default 8 years)
   - Replacement cost input (default 18 000€)

2. **Add car flow:**
   - Dialog/inline: name + fuel type + acquisition date/age + replacement cycle + replacement cost
   - POST with `entity_type: "car"`, `metadata: {"fuel_type": "petrol", "replace_cycle": 8, "replace_cost": 18000}`
   - Backend generates: assurance, carburant (amount varies by fuel type), entretien, CT events at ages 4/6/8..., replacement event

3. **Fuel type affects defaults:**
   - Petrol: carburant ~1 200€/year
   - Diesel: carburant ~1 000€/year
   - Electric: carburant ~400€/year (electricity), but entretien lower (~200€/year vs ~400€)
   - Hybrid: carburant ~800€/year

4. **CT events in the list** show as individual one-time events ("CT 4 ans: 80€", "CT 6 ans: 80€") — visually distinct from recurring costs. The CostEventList already handles `frequency: "once"`.

5. **Replacement cycle / cost editable in metadata:** Changing these should ideally regenerate the CT events and replacement event. For MVP, just show a note: "Modifiez les événements manuellement si vous changez le cycle."

### Tech Section (sky accent Card, "Tech 💻")

6. For each tech entity: `LifeEntityCard` with header:
   - Name input ("MacBook Pro", "iPhone")
   - Device type: implicit from name (no select needed — the name IS the device)
   - Acquisition date or approximate age
   - Replacement cycle input (default: 3 for phones, 4 for laptops)
   - Estimated replacement cost input

7. **Add tech flow:**
   - Dialog/inline: name + age + replacement cycle + replacement cost
   - POST with `entity_type: "tech"`, `metadata: {"replace_cycle": 4, "replace_cost": 2500}`
   - Backend generates: replacement events at cycle intervals, accessories/repair annual cost

8. **Tech cost events are simpler:** mainly replacement events + small annual accessories budget. The CostEventList shows them the same way as other entities.

9. i18n keys under `life.cars.*` and `life.tech.*`

## Technical Approach

### Files to Modify
- `frontend/src/routes/(app)/life/+page.svelte` — add cars and tech sections
- `frontend/src/locales/fr.json` — add keys

### Car/Tech Header Patterns
Cars have more metadata fields than other entities (fuel type, cycle, replacement cost). The LifeEntityCard header slot handles this — just pass more inputs.

For tech, the pattern is even simpler — fewer fields, fewer events. The card will be compact.

## Acceptance Criteria

- [ ] Adding a petrol car generates: assurance 600€/yr, carburant 1200€/yr, entretien 400€/yr, CT at ages 4/6/8, replacement at age 8
- [ ] Adding an electric car: carburant 400€/yr, entretien 200€/yr
- [ ] CT events appear as individual one-time items in the cost event list
- [ ] Adding tech with cycle=3, cost=1300 generates replacement events at ages 3, 6, 9, 12...
- [ ] Fuel type select changes are saved to entity metadata
- [ ] Replacement cycle/cost editable in card header
- [ ] Both sections render with correct accent colors (amber/sky)
- [ ] Multiple cars and tech items display without layout issues
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] Smoke test: add car age 5, cycle 8 → CT at 6 and 8 visible as future events, assurance active
- [ ] LEARNINGS.md updated

## Notes

- Electric vs petrol is a big long-term cost difference. The prototype mentioned the idea of "maybe time to think about electric" — that's Sprint 5 AI territory. For now, the raw numbers speak for themselves.
- Tech replacement costs should be at 2026 prices. The projection engine (Sprint 4) inflation-adjusts them. Don't double-inflate by putting inflated costs in the defaults.
- Some users will have 2-3 cars (family + work) and 4-5 tech items (laptop, phone, tablet, monitor, etc.). The UI should handle 5+ items per section gracefully — probably a scrollable list within the card rather than unbounded vertical growth.
