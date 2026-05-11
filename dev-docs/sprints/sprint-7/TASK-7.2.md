# TASK-7.2: Bug Fix — BRUT/NET Labels

**Status:** DONE — Already implemented. Identity page has dynamic `salaryLabel` with BRUT labels per period type (lines 106-116) and "€ brut/an" in period list (line 409). Revenue page has "CA brut mensuel (€)" label (line 128) and "Avant cotisations sociales et impôts" hint (line 141).
**Sprint:** 7
**Priority:** P0 (UX clarity)
**Est. effort:** 30 min
**Dependencies:** None

---

## Context

Two places ask for salary/revenue numbers without specifying BRUT or NET:
1. Career history form on the Identity page — input placeholder says "Salaire/CA annuel"
2. Revenue page — CA input doesn't explicitly say "brut"

For CDI periods, the pension engine needs salaire brut. For AE periods, it needs CA brut (before cotisations). A user entering NET instead of BRUT will get a wrong pension estimate.

---

## Step-by-Step Instructions

### Step 1: Career history form — dynamic label

File: `frontend/src/routes/(app)/identity/+page.svelte`

Find the career form salary input (search for `newCareerSalary` or `"Salaire/CA annuel"`).

Replace the static placeholder with a reactive label based on `newCareerType`:

```svelte
{@const salaryLabel = {
  cdi: 'Salaire brut annuel',
  cdd: 'Salaire brut annuel',
  ae: 'CA brut annuel',
  sasu: 'Rémunération brute annuelle',
  unemployment: 'ARE brute annuelle',
  parental_leave: 'Indemnités brutes',
}[newCareerType] || 'Revenu brut annuel'}

<input type="number" bind:value={newCareerSalary} min="0" step="1000"
  placeholder={salaryLabel}
  class="w-28 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
```

### Step 2: Career period display — show "brut" in the listed periods

In the career periods list (the `{#each careerPeriods as period}` block), the salary displays as:

```svelte
{parseFloat(period.annual_gross).toLocaleString('fr-FR')}€/an
```

Change to:

```svelte
{parseFloat(period.annual_gross).toLocaleString('fr-FR')}€ brut/an
```

### Step 3: Revenue page CA input

File: `frontend/src/routes/(app)/revenue/+page.svelte`

Find the CA input. Its label should include "brut". If the label says "CA mensuel" or similar, change to "CA brut mensuel". Add a hint below:

```svelte
<p class="text-[10px] text-zinc-500 mt-1">Avant cotisations sociales et impôts</p>
```

### Step 4: i18n keys

Add to `frontend/src/locales/fr.json` under `career.*`:

```json
"salary_labels": {
  "cdi": "Salaire brut annuel",
  "cdd": "Salaire brut annuel",
  "ae": "CA brut annuel",
  "sasu": "Rémunération brute annuelle",
  "unemployment": "ARE brute annuelle",
  "parental_leave": "Indemnités brutes annuelles",
  "default": "Revenu brut annuel"
},
"salary_hint": "Montant brut, avant cotisations et impôts"
```

Add to `revenue.*`:
```json
"ca_label": "CA brut mensuel",
"ca_hint": "Avant cotisations sociales et impôts"
```

Mirror in `en.json`.

---

## SCOPE BOUNDARY

- DO NOT change the backend salary field or validation.
- DO NOT add new input fields. This is labels-only.
- DO NOT restructure the career form layout.
- Expected change: ~15 lines across 3 files (identity page, revenue page, locale files).

## DONE WHEN

- [ ] Career form placeholder changes dynamically when period type changes
- [ ] Career period list shows "brut/an" after the amount
- [ ] Revenue CA input label explicitly says "brut"
- [ ] Hint text visible below both inputs
- [ ] i18n keys in both fr.json and en.json
- [ ] No console warnings about missing i18n keys
