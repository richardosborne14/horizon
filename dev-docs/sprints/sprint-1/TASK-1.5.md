# TASK-1.5: Identity Frontend Section

**Status:** BACKLOG
**Sprint:** 1
**Priority:** P0 (critical)
**Est. effort:** 2 hr
**Dependencies:** TASK-1.1, TASK-1.2, TASK-0.4

## Context

The first section a user interacts with after onboarding. Sets their financial identity: age, retirement target, fiscal parts, AE status, activity type, versement libératoire. Shows the projected cotisation rate schedule so the user understands rates aren't flat. Maps directly to the prototype's Identity section — two cards ("Vous" and "Statut & Activité") with a rate schedule preview.

**Prototype reference:** `horizon30.jsx` → `Identity` component. Two Card components with accent borders (teal and amber). Rate schedule preview as a row of year/rate pairs.

## Requirements

1. Replace placeholder in `frontend/src/routes/(app)/identity/+page.svelte`

2. **`+page.server.ts`**: Load user profile via `GET /api/profile` and AE rate schedule via `GET /api/rates/ae-schedule?type={profile.ae_activity_type}`

3. **Card 1 — "Vous" (teal accent):**
   - Birth date input (date picker or day/month/year fields) → derives displayed age
   - Target retirement age input (number, 50-85)
   - Tax parts input (number, step 0.5, min 1.0) with hint: "1=seul · 2=couple · +0.5/enfant · +1 au 3ème"
   - All fields auto-save on change (debounce 800ms via `PUT /api/profile`)
   - Subtle "✓" save confirmation (reuse ComCoi pattern if still in codebase)

4. **Card 2 — "Statut & Activité" (amber accent):**
   - Status select: AE, EIRL, EURL, SASU
   - Activity type select: 4 AE types with rate hints in option labels
   - VL checkbox with explanation text and current combined rate display
   - Rate schedule preview component: row of year → rate badges, re-fetched when activity type changes
   - Small grey text: "Projections basées sur les tendances législatives"

5. **Auto-save pattern:**
   - Debounce 800ms after any input change
   - `PUT /api/profile` with only changed fields
   - Show subtle save indicator (not a spinner — just a brief "✓ Enregistré" that fades)
   - On error: show toast, don't lose the user's input

6. **i18n keys** under `identity.*`:
   - `identity.card_you`, `identity.card_status`
   - `identity.birth_date`, `identity.target_age`, `identity.tax_parts`, etc.
   - `identity.vl_label`, `identity.vl_hint`
   - `identity.rate_schedule_title`, `identity.rate_schedule_hint`

## Technical Approach

### Files to Create/Modify
- `frontend/src/routes/(app)/identity/+page.svelte` — full implementation
- `frontend/src/routes/(app)/identity/+page.server.ts` — data loading
- `frontend/src/lib/components/RateSchedulePreview.svelte` — reusable component
- `frontend/src/lib/components/AutoSaveInput.svelte` — reusable debounced input (if not already exists)
- `frontend/src/locales/fr.json` — add `identity.*` keys
- `frontend/src/locales/en.json` — add `identity.*` keys

### Component Pattern (from prototype)
```svelte
<Card title={$t('identity.card_you')} icon="👤" accent="teal">
  <div class="grid grid-cols-3 gap-4">
    <Inp label={$t('identity.birth_date')} ... />
    <Inp label={$t('identity.target_age')} ... />
    <Inp label={$t('identity.tax_parts')} ... />
  </div>
</Card>
```

Create reusable `Card.svelte` and `Inp.svelte` (or `FormInput.svelte`) components matching the prototype's styling. These will be reused across all sections.

## Acceptance Criteria

- [ ] Page loads with profile data pre-filled (or defaults for new user)
- [ ] Changing birth date updates displayed age reactively
- [ ] Changing activity type re-fetches and displays new rate schedule
- [ ] VL toggle updates the displayed combined rate
- [ ] All inputs auto-save after 800ms debounce
- [ ] Save confirmation appears briefly ("✓")
- [ ] Rate schedule shows projected rates for selected activity type
- [ ] All text from i18n keys (no hardcoded strings in template)
- [ ] Dark theme: zinc-950 bg, teal/amber accent borders, zinc-900/60 inputs
- [ ] Smoke test: change birth date → age updates; change AE type → rates update; refresh page → values persisted
- [ ] LEARNINGS.md updated

## Notes

- Birth date UX: a standard `<input type="date">` is fine for MVP. The dark theme will need CSS to style the native date picker (or use a simple 3-field day/month/year approach).
- The rate schedule preview is a simple component — a flex row of small cards showing year and rate. It fetches from `/api/rates/ae-schedule` and re-renders when the activity type prop changes.
- The "info box" pattern from the prototype (colored bg with 💡 icon) should be a reusable `InfoBox.svelte` component. Used here for the VL explanation and rate schedule caveat.
