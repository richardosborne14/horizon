# TASK-5.8: Onboarding Flow & Progress Tracking

**Status:** TODO
**Sprint:** 5
**Priority:** P2 (medium — UX polish, not blocking core value)
**Est. effort:** 2 hr
**Dependencies:** None

## Context

A new user lands on the Identity page with empty fields and no guidance. They have 7 sections to fill, no sense of priority, and no encouragement. The sidebar green dots indicate completion but don't explain what's needed or why. For a tool that requires thoughtful data entry to deliver value, the first 10 minutes are critical — if the user bounces during setup, the projection engine never gets to shine.

## Requirements

### Onboarding Welcome Screen

1. **First-login detection:** If the user has no profile data (no birth_date set), show a welcome overlay on the Runway page:
   - "Bienvenue sur Horizon"
   - Brief explanation: "Horizon projette votre patrimoine sur 30 ans. Commencez par renseigner votre profil — chaque section ajoute de la précision à votre projection."
   - "Commencer" button → navigates to Identity

2. **Skip option:** "Explorer d'abord" → dismisses the overlay, lets user browse freely. Don't be pushy.

### Section Progress Tracker

3. **Enhance sidebar section indicators** from simple green dots to a progress system:
   
   | Status | Visual | Meaning |
   |--------|--------|---------|
   | Empty | ○ gray dot | No data entered |
   | Partial | ◐ half-teal dot | Some fields filled |
   | Complete | ● teal dot | All required fields filled |
   
   "Required fields" per section:
   - **Identité:** birth_date, ae_activity_type (2 fields)
   - **Revenus:** monthly_gross_ca, growth_preset (2 fields)
   - **Charges:** at least 3 expense categories > 0 (3 fields)
   - **Vie:** no required fields (optional section)
   - **Épargne:** at least 1 vehicle with monthly_contribution > 0 (1 field)
   - **Projets:** no required fields (optional section)
   - **Horizon:** birth_date must be set (dependency on Identity)

4. **Progress bar** at the top of the app (thin teal bar below the header):
   - Shows completion percentage across all sections
   - "3/5 sections complétées" text on hover
   - Fills from left to right as sections are completed
   - Disappears once all required sections are complete (don't clutter the UI permanently)

### Section-Level Guidance

5. **Empty state for each section** — when a section has no data, show a helpful card:
   - Icon + title + 2-sentence explanation of what this section does and why it matters
   - "Why it matters" angle: "Sans vos charges, la projection surestime votre net de 3 700€/mois"
   - Quick-fill button (optional): "Remplir avec des valeurs moyennes" for Charges (pre-fills with national averages)

6. **Section completion toast:** When a section transitions from partial to complete, show a brief toast: "✓ Revenus complétés — votre projection est maintenant plus précise."

### Guided Flow (Optional Enhancement)

7. **"Next section" prompt** at the bottom of each completed section:
   - "Section suivante : Revenus →" with a subtle teal link
   - Only shown when the next section is empty/partial
   - Follows the logical order: Identité → Revenus → Charges → Vie → Épargne → Projets → Horizon

### Backend

8. **Add completion check endpoint** `GET /api/profile/completion`:
   ```json
   {
     "overall_pct": 60,
     "sections": {
       "identity": { "status": "complete", "missing": [] },
       "revenue": { "status": "complete", "missing": [] },
       "expenses": { "status": "partial", "missing": ["at_least_3_categories"] },
       "life": { "status": "empty", "missing": [], "optional": true },
       "savings": { "status": "empty", "missing": ["monthly_contribution"] },
       "projects": { "status": "empty", "missing": [], "optional": true }
     }
   }
   ```

9. **Store onboarding state:** Add `onboarding_dismissed` boolean to UserProfile (so the welcome screen doesn't reappear).

## Acceptance Criteria

- [ ] Welcome screen shows for new users with no profile data
- [ ] Welcome screen can be dismissed and doesn't reappear
- [ ] Sidebar dots reflect actual section completion status
- [ ] Progress bar shows overall completion percentage
- [ ] Empty state cards render in sections with no data
- [ ] Completion toast fires when a section transitions to complete
- [ ] "Next section" prompt guides the user through setup
- [ ] Completion API returns accurate status for all sections
- [ ] Progress bar disappears after all required sections are complete
- [ ] LEARNINGS.md updated

## Notes

- The onboarding should feel inviting, not bureaucratic. It's "let me help you get started" not "you must fill these forms."
- The quick-fill option for Charges is particularly valuable — entering 12 expense categories is tedious. National average values (from INSEE data) give a reasonable starting point.
- Don't block access to the Runway page during onboarding. Let users see the projection even with incomplete data — the projection engine handles missing data gracefully. Seeing a rough projection early motivates completing the rest.
- The section progress dots in the sidebar are already there as green dots — this task refines them from binary (done/not-done) to three states.
