# TASK-2.2: Canned Defaults Service

**Status:** BACKLOG
**Sprint:** 2
**Priority:** P0 (critical)
**Est. effort:** 2 hr
**Dependencies:** TASK-2.1

## Context

When a user adds a life entity, they shouldn't face a blank slate. The system pre-populates reasonable French cost defaults based on the entity type and age. For kids, this includes the **French September school entry rule** — a child born before September enters maternelle the September they turn 3; a child born September-December enters the following September (effectively age ~3.75).

This is the "progressive calculation" foundation. The canned defaults encode real-world lifecycle knowledge: kids age through school stages, pets have vaccination schedules, cars need CT inspections, tech depreciates and gets replaced.

## Requirements

1. Create `backend/app/services/canned_defaults.py`

2. **`get_kid_defaults(birth_date: date) -> list[CostEvent]`:**

   French school system stages:
   - **Crèche / Garde** (birth → maternelle entry): ~500€/month
   - **Maternelle** (entry age ~3 → age 6): cantine ~100€/month
   - **Primaire** (6→11): cantine + périscolaire ~150€/month
   - **Collège** (11→15): cantine ~150€/month, fournitures ~400€/year
   - **Lycée** (15→18): cantine ~150€/month, fournitures ~600€/year
   - **Camp d'été** (6→17): ~800€/year
   - **Activités extra-scolaires** (6→18): ~100€/month
   - **Permis de conduire** (18→18): ~1 800€ one-time
   - **Première voiture** (18→18): ~5 000€ one-time (or combined as "Permis + voiture" ~6 800€)
   - **Études supérieures** (18→23): ~500€/month (logement, frais, vie étudiante)

   **September rule implementation:**
   ```python
   def _maternelle_entry_age(birth_date: date) -> int:
       """
       French rule: children enter maternelle the September of the year they turn 3.
       Born Jan-Aug → enters September same year they turn 3 (effectively age 3.0-3.7)
       Born Sep-Dec → enters September next year (effectively age 3.75-4.0)
       
       For cost event purposes, we use from_age based on this:
       - Crèche runs from age 0 to maternelle entry age
       - Maternelle/cantine starts at entry age
       """
       turns_3_year = birth_date.year + 3
       if birth_date.month >= 9:  # Sep-Dec birth
           entry_year = turns_3_year + 1
       else:  # Jan-Aug birth
           entry_year = turns_3_year
       # Return approximate age at entry (for from_age bracket)
       entry_date = date(entry_year, 9, 1)
       age_at_entry = (entry_date - birth_date).days // 365
       return age_at_entry  # Will be 3 or 4
   ```

   Generate cost events using computed entry age for the crèche→maternelle transition.

3. **`get_pet_defaults(pet_type: str, birth_date: date) -> list[CostEvent]`:**

   - **Nourriture** (0→lifespan): dog ~600€/year, cat ~400€/year
   - **Vétérinaire annuel** (1→lifespan): ~200€/year
   - **Vaccins primo** (0→1): ~250€ one-time
   - **Rappel vaccins** (1→lifespan): ~80€/year
   - **Stérilisation** (0→1): ~300€ one-time (dog), ~200€ (cat)
   - **Toilettage** (0→lifespan, dog only): ~300€/year
   - **Soins vieux** (lifespan-3→lifespan): extra ~400€/year
   
   Lifespan: dog=13, cat=18, other=12

4. **`get_car_defaults(fuel_type: str, acquisition_date: date, replace_cycle: int = 8, replace_cost: Decimal = 18000) -> list[CostEvent]`:**

   - **Assurance** (0→cycle): ~600€/year
   - **Carburant** (0→cycle): petrol ~1200€/year, diesel ~1000€/year, electric ~400€/year, hybrid ~800€/year
   - **Entretien courant** (0→cycle): ~400€/year
   - **Contrôle technique** (4→cycle, every 2 years): ~80€/event — generate multiple "once" events at ages 4, 6, 8...
   - **Remplacement véhicule** (cycle→cycle): replace_cost, one-time
   
   Note: CT events are generated as individual one-time events at specific ages, not a recurring bracket, because CT happens at fixed intervals.

5. **`get_tech_defaults(device_type: str, acquisition_date: date, replace_cycle: int = 3, replace_cost: Decimal = 1200) -> list[CostEvent]`:**

   - **Remplacement** (cycle→cycle): replace_cost, one-time — generate events at ages cycle, cycle*2, cycle*3 (up to 30 years out)
   - **Accessoires / réparations** (0→30): ~50€/year for phone, ~100€/year for laptop
   - **Assurance / AppleCare** (0→cycle): ~100€/year for laptop, ~60€/year for phone

6. **Integration with CRUD:** When `POST /api/life-entities` is called with empty `cost_events`, call the appropriate defaults function and populate the entity before saving.

7. **All defaults labeled** `source: "default"` so UI can distinguish them from user-added events.

8. Unit tests:
   - September rule: kid born 2025-03-15 → crèche ends at age 3, kid born 2025-10-01 → crèche ends at age 4
   - Pet defaults generate correct lifespan-based events
   - Car CT events appear at correct ages
   - Tech replacement events generated for 30-year horizon

## Technical Approach

### Files to Create
- `backend/app/services/canned_defaults.py`
- `backend/app/routers/life_entities.py` — modify POST to call defaults
- `backend/tests/test_canned_defaults.py`

### Key Implementation Detail
The defaults functions return `list[CostEvent]` (Pydantic models). The router converts them to dicts for JSONB storage. Each event gets a unique `id` (8-char UUID prefix) so the frontend can identify individual events for editing.

## Acceptance Criteria

- [ ] Kid born 2025-03-15: crèche from_age=0, to_age=3 (enters maternelle Sept 2028)
- [ ] Kid born 2025-10-01: crèche from_age=0, to_age=4 (enters maternelle Sept 2029)
- [ ] Kid defaults include all 10+ cost events from crèche through études
- [ ] Pet defaults include vaccination, sterilisation, old-age care
- [ ] Dog defaults include toilettage, cat defaults do not
- [ ] Car CT events generated at ages 4, 6, 8 (for cycle=8)
- [ ] Car replacement event at age=replace_cycle
- [ ] Tech replacement events at cycle, cycle*2, cycle*3...
- [ ] All events have `source: "default"` and unique IDs
- [ ] POST /api/life-entities with empty cost_events → populated from defaults
- [ ] POST /api/life-entities with provided cost_events → uses those (no defaults)
- [ ] Unit tests pass for September rule edge cases
- [ ] LEARNINGS.md updated

## Notes

- The amounts are national averages for France. They're deliberately round numbers (500, 150, 800) because precision is false — the user is expected to adjust to their reality. The value is in the structure (knowing WHICH costs exist at WHICH ages), not the exact amounts.
- The September rule is simplified. In reality there are exceptions (TPS at 2 years, some communes have different rules). The simplified version covers 95% of cases. Document this in a code comment.
- For car CT: generating individual "once" events is more explicit than a recurring bracket. It makes the projection engine simpler (no "every 2 years" logic needed — just walk the list) and the UI clearer (the user sees "CT à 4 ans: 80€, CT à 6 ans: 80€" rather than "CT tous les 2 ans").
- Tech replacement costs should increase with inflation in the projection engine (Sprint 4), not in the defaults. The defaults store 2026 prices.
