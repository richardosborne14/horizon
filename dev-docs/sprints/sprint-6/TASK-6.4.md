# TASK-6.4: Car Lifecycle Overhaul

**Status:** TODO
**Sprint:** 6
**Priority:** P0 (critical — both cars contribute zero to projection)
**Est. effort:** 2 hr
**Dependencies:** None

## Context

The audit revealed that both of Richard's cars (Xsara age 15, Peugeot age 19) contribute exactly 0€ to the projection across all 30 years. Every cost event has `to_age: 8`, but both entities are already past age 8 at projection start. The engine correctly checks `entity_age >= from_age and entity_age <= to_age` — and since 15 > 8 and 19 > 8, no events fire.

This means the projection assumes zero fuel, zero insurance, zero maintenance, and zero replacement costs for 30 years. That's easily 3,000€/year in ongoing costs plus periodic 18,000€ replacement events — roughly 100–150k€ of missing expenses over the projection period.

The fix has two parts: (1) handle expired entities immediately, and (2) redesign how cars work so old cars don't silently disappear.

## Requirements

### Part 1: Detect & Fix Expired Entities

1. **Add expired entity detection** to the projection router:
   ```python
   # When assembling life entities for projection input:
   for entity in entities:
       entity_age = compute_age(entity.reference_date, today)
       max_to_age = max(evt["to_age"] for evt in entity.cost_events) if entity.cost_events else 0
       
       if entity_age > max_to_age:
           # Entity is expired — all cost events are in the past
           entity_data["expired"] = True
           entity_data["expired_since_age"] = max_to_age
   ```

2. **API: Add expired flag** to `GET /api/life-entities` response:
   ```json
   {
     "id": "xxx",
     "name": "Xsara (2010)",
     "entity_type": "car",
     "current_age": 15,
     "expired": true,
     "expired_message": "Tous les coûts prévus sont terminés (dernier à l'âge 8). Ce véhicule ne contribue pas à la projection.",
     "suggested_action": "replace_or_archive"
   }
   ```

3. **Frontend: Visual indicator** for expired entities:
   - Amber border on the entity card
   - Warning message: "Ce véhicule a dépassé son cycle de vie (15 ans > 8 ans max). Il ne génère aucun coût dans la projection."
   - Two action buttons:
     - "Mettre à jour le cycle" → opens form to extend/replace cost events
     - "Archiver" → soft-delete the entity

### Part 2: Rolling Replacement Model for Cars

4. **New car lifecycle approach — "continuous ownership":**

   Instead of modeling a specific car from purchase to junkyard, model the *concept of owning a car*. The user has a car. It costs money every year. It gets replaced periodically. The costs never stop (until the user decides to stop owning a car).

   **New cost event structure for cars:**
   ```json
   [
     { "label": "Assurance auto", "from_age": 0, "to_age": 99, "amount": 600, "frequency": "annual" },
     { "label": "Carburant / Énergie", "from_age": 0, "to_age": 99, "amount": 1200, "frequency": "annual" },
     { "label": "Entretien courant", "from_age": 0, "to_age": 99, "amount": 400, "frequency": "annual" },
     { "label": "Contrôle technique", "from_age": 4, "to_age": 4, "amount": 80, "frequency": "once" },
     { "label": "Contrôle technique", "from_age": 6, "to_age": 6, "amount": 80, "frequency": "once" },
     { "label": "Remplacement véhicule", "from_age": 8, "to_age": 8, "amount": 18000, "frequency": "once" },
     { "label": "Remplacement véhicule", "from_age": 16, "to_age": 16, "amount": 18000, "frequency": "once" },
     { "label": "Remplacement véhicule", "from_age": 24, "to_age": 24, "amount": 18000, "frequency": "once" },
     { "label": "Remplacement véhicule", "from_age": 32, "to_age": 32, "amount": 18000, "frequency": "once" }
   ]
   ```

   The key change: `to_age: 99` on ongoing costs (insurance, fuel, maintenance) instead of `to_age: 8`. The entity represents "I own a car" not "I own this specific car."

5. **CT cycle follows the car's actual age, not the entity's age:**
   - CT is due at car age 4, then every 2 years
   - When the car is replaced (at entity age 8, 16, 24...), the CT cycle resets
   - For MVP: pre-generate CT events at the appropriate ages relative to each replacement cycle

6. **"How long do you plan to own cars?" input:**
   - Add a toggle on the car entity: "Véhicule permanent" (ongoing costs until retirement) vs "Dernière voiture" (costs end at a specific year)
   - Default: permanent (most people own cars until retirement or beyond)

### Part 3: Fix Existing Entities on Migration

7. **Migration script for existing car entities:**
   - Detect car entities where `max(to_age) < current_entity_age`
   - For each expired car, auto-extend ongoing cost events to `to_age: 99`
   - Add future replacement events at `replace_cycle` intervals from the current age
   - Flag the entity for user review: "Nous avons étendu le cycle de vie de votre {name}. Vérifiez les coûts."
   - **Do NOT auto-migrate silently** — prompt the user on their next visit to the Vie page

8. **Prompt on Vie page:**
   - If expired car entities exist, show a top-of-page alert:
     - "Votre {Xsara} et {Peugeot} sont au-delà de leur cycle de vie. Les coûts ne sont pas pris en compte dans votre projection."
     - "Possédez-vous toujours ces véhicules ? [Oui, mettre à jour] [Non, archiver]"
   - "Oui" → auto-extend cost events to cover ongoing costs + future replacements
   - "Non" → soft-delete the entity

### Part 4: Canned Defaults Update

9. **Update `backend/app/services/canned_defaults.py`** (or wherever car defaults live):
   - New car defaults should use `to_age: 99` for ongoing costs
   - Replacement events pre-generated at 8-year intervals up to entity age 40
   - CT events generated relative to each replacement cycle
   - When user creates a new car, the defaults reflect the rolling model

10. **Display improvement:**
    - On the Vie page, show a "Prochain remplacement" indicator on each car card
    - Show the annual cost summary: "~2,200€/an + remplacement à {year}"

## Acceptance Criteria

- [ ] Expired entity detection works (identifies entities where all cost events are past)
- [ ] API returns expired flag and message for expired entities
- [ ] Frontend shows amber warning on expired car cards with action buttons
- [ ] New car lifecycle uses to_age: 99 for ongoing costs
- [ ] Replacement events generate at replace_cycle intervals
- [ ] Existing expired cars prompt user for action on Vie page
- [ ] "Oui, mettre à jour" extends costs and adds future replacements
- [ ] "Non, archiver" soft-deletes the entity
- [ ] Projection now shows non-zero car expenses when cars are properly configured
- [ ] Car expense of ~2,200€/year (insurance + fuel + maintenance) appears in projection
- [ ] Replacement events of ~18,000€ appear at correct intervals
- [ ] Unit tests for expired detection, rolling replacement, CT cycles
- [ ] LEARNINGS.md updated

## Notes

- This is probably the most impactful accuracy fix in Sprint 6. Adding ~2,200€/year of ongoing car costs plus periodic 18,000€ replacements could shift the wealth-at-retirement figure by 80–120k€ downward. That's a huge correction.
- The same expired-entity problem could theoretically affect pets and tech, but in practice: pets have `to_age: 13` and start young (age 1 for Layla → 12 years of costs remaining), and tech entities have events up to age 30 with aggressive replacement cycles. Cars are uniquely vulnerable because they use a short `to_age: 8` combined with entities that are commonly older than 8 at entry.
- Consider adding a "sell car" event — when replacing, the old car has residual value (e.g., 3,000€ trade-in) that offsets the replacement cost. For MVP, ignore residual value. Add in a future sprint.
