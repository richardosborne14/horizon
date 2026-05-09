# TASK-3.6: Projects Frontend — Status Change + Page Assembly

**Status:** BACKLOG
**Sprint:** 3
**Priority:** P1 (high)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-3.4, TASK-3.5

## Context

The status change simulation is the "structural optimisation" lever — "what if I switch from AE to EIRL in 2028 and deduct real expenses?" The fields already live on the UserProfile (TASK-1.1: `status_change_enabled`, `status_change_year`, `status_change_target`, `status_change_savings`). This task builds the UI for those fields and assembles the full Projects page with all three sections: investments, life events, and status change.

**Prototype reference:** `horizon30.jsx` → `Projects` → third Card ("Changement de statut juridique 🔄"). Enable toggle, year/status/savings inputs, explanatory text about EIRL deduction logic.

## Requirements

### Status Change Section

1. Add section to `(app)/projects/+page.svelte` (teal accent Card, "Changement de statut juridique 🔄"):

2. **Explanatory text** (from prototype, adapted):
   > AE → EIRL/EURL : vous pouvez déduire vos vraies charges professionnelles du CA avant cotisations.
   > Exemple : internet 50€ + bureau/home office 200€ + voiture pro 250€ + repas midi 150€ = 650€/mois = 7 800€/an déductibles.
   > Si vos charges réelles dépassent l'abattement forfaitaire AE de 34% (BNC), votre base imposable baisse → vous gardez plus.

3. **Enable toggle:** checkbox + "Simuler un changement de statut"
   - When unchecked: inputs hidden, projection ignores status change
   - When checked: inputs visible

4. **3-column input row** (visible when enabled):
   - Année du changement (number input, default 2028)
   - Nouveau statut (select: EIRL/EI, EURL, SASU)
   - Économie nette annuelle (number input, €/an) — hint: "Gain annuel estimé vs rester AE après déduction des vraies charges"

5. **All inputs save to UserProfile** via `PUT /api/profile` (these are profile fields, not a separate model)

6. **Quick EIRL calculator helper** (optional enhancement):
   If time permits, add an expandable "Estimez votre économie" section:
   - Small input grid: internet/mois, bureau/mois, voiture/mois, repas/mois, autres/mois
   - Sum = total charges déductibles annuelles
   - Compare: `abattement_forfaitaire = CA * 0.34` vs `charges_reelles`
   - If charges_reelles > abattement → show: "Vos charges réelles ({fmt}) dépassent l'abattement ({fmt}) de {fmt}. L'EIRL vous ferait économiser ~{fmt}/an en cotisations."
   - This is a client-side preview calculation, not stored — just helps the user fill in the "économie nette" field

### Page Assembly

7. Verify the full Projects page renders all 3 sections in order:
   1. Investments (emerald accent) — from TASK-3.4
   2. Life events (amber accent) — from TASK-3.5
   3. Status change (teal accent) — this task

8. Consistent spacing: `space-y-5`

9. **Sidebar wiring:** "Projets" count in sidebar = count of active investment projects (not events, not status change). Invalidate profile summary store on project add/remove.

10. **Page data loading:** `+page.server.ts` loads projects (one API call) + profile (for status change fields). Split projects into investments and events client-side.

11. i18n keys under `projects.status.*`

## Technical Approach

### Files to Modify
- `frontend/src/routes/(app)/projects/+page.svelte` — add status change section + verify assembly
- `frontend/src/routes/(app)/projects/+page.server.ts` — load profile alongside projects
- `frontend/src/lib/stores/profile-summary.ts` — invalidate on project changes
- `frontend/src/locales/fr.json` — add `projects.status.*` keys

### Status Change Save Pattern
The status change fields are on the profile, not the project model. Save via `PUT /api/profile`:
```javascript
async function saveStatusChange() {
  await api.put('/profile', {
    status_change_enabled: enabled,
    status_change_year: year,
    status_change_target: target,
    status_change_savings: savings,
  });
}
```

### Quick EIRL Calculator (optional)
```svelte
{#if showEstimator}
  <div class="grid grid-cols-5 gap-2 mt-3">
    <Inp label="Internet" bind:value={est.internet} suffix="€/m" />
    <Inp label="Bureau" bind:value={est.bureau} suffix="€/m" />
    <Inp label="Voiture" bind:value={est.voiture} suffix="€/m" />
    <Inp label="Repas" bind:value={est.repas} suffix="€/m" />
    <Inp label="Autres" bind:value={est.autres} suffix="€/m" />
  </div>
  {#if totalCharges > abattement}
    <p class="text-xs text-teal-300 mt-2">
      ✓ Vos charges réelles ({fmt(totalCharges)}/an) dépassent l'abattement
      ({fmt(abattement)}/an). Économie potentielle : ~{fmt(economie)}/an
    </p>
  {:else}
    <p class="text-xs text-amber-300 mt-2">
      Vos charges réelles ({fmt(totalCharges)}/an) sont inférieures à l'abattement
      ({fmt(abattement)}/an). L'AE reste plus avantageux pour l'instant.
    </p>
  {/if}
{/if}
```

## Acceptance Criteria

- [ ] Status change toggle enables/disables the section
- [ ] Year, target status, and savings save to profile
- [ ] Explanatory text renders clearly with the EIRL deduction example
- [ ] All 3 sections render on Projects page in correct order
- [ ] Spacing consistent
- [ ] Sidebar "Projets" count shows investment project count
- [ ] Page loads with 2 API calls (projects + profile)
- [ ] Quick EIRL calculator (if implemented): correctly compares charges vs abattement
- [ ] All text via i18n keys
- [ ] Dark theme matches prototype
- [ ] Smoke test: enable status change → set year 2028, EIRL, 3600€ savings → refresh → persisted → toggle off → refresh → still disabled
- [ ] LEARNINGS.md updated

## Notes

- The status change simulation is critical for users who are close to the threshold where real deductions beat the AE forfait. For a BNC freelancer earning 40k, the 34% abattement is 13 600€. If real pro expenses exceed that, EIRL wins. The quick calculator helps users figure this out without a spreadsheet.
- The EIRL estimator is optional polish. If it's too complex for this sprint, the user can calculate their estimated savings externally and just enter the number. The important thing is the field exists and feeds into the projection engine.
- The projection engine (Sprint 4) applies `status_change_savings` as additional disposable income from `status_change_year` onward. Simple addition — no complex EIRL tax simulation needed for MVP.
- Social charges under EIRL/EURL are ~45% on net remuneration (TNS) which is higher than AE rates, BUT you're taxed on a lower base (CA minus real expenses). The net effect depends on the expense/CA ratio. This nuance is worth a tooltip but not a full calculator in MVP.
