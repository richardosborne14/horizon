# TASK-7.9: Couple Frontend — Identity & Revenue Integration

**Status:** TODO
**Sprint:** 7
**Priority:** P2 (medium)
**Est. effort:** 2.5 hr
**Dependencies:** TASK-7.4, TASK-7.6, TASK-7.7

---

## Context

Wire spouse data into the Identity page (spouse card, career timeline), the Revenue page (spouse sources already handled by earner filter in 7.6), the Runway page (household stats), and the sidebar (household CA).

---

## Step-by-Step Instructions

### Step 1: Identity page — Spouse card

File: `frontend/src/routes/(app)/identity/+page.svelte`

Add a third card after "Statut & Activité" — the "Conjoint(e)" card (purple accent).

**If no spouse exists:**
```svelte
<Card title="Conjoint(e)" icon="💑" accent="purple">
  <p class="text-xs text-zinc-500 mb-3">Ajoutez votre conjoint(e) pour une projection du foyer.</p>
  <button on:click={createSpouse}
    class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-purple-700/50">
    + Ajouter un conjoint
  </button>
</Card>
```

**If spouse exists:**
```svelte
<Card title="Conjoint(e) — {spouse.first_name || 'Sans nom'}" icon="💑" accent="purple">
  <div class="grid grid-cols-2 gap-3">
    <Inp label="Prénom" bind:value={spouse.first_name} on:input={debouncedSaveSpouse} />
    <Inp label="Date de naissance" type="date" bind:value={spouse.birth_date} on:input={debouncedSaveSpouse} />
    <select bind:value={spouse.relationship_type} on:change={debouncedSaveSpouse}
      class="...input-classes...">
      <option value="married">Marié(e)</option>
      <option value="pacsed">PACSé(e)</option>
      <option value="concubinage">Concubinage</option>
    </select>
    <select bind:value={spouse.status} on:change={debouncedSaveSpouse}
      class="...input-classes...">
      <option value="cdi">CDI</option>
      <option value="cdd">CDD</option>
      <option value="ae">Auto-entrepreneur</option>
      <option value="retired">Retraité(e)</option>
      <option value="inactive">Inactif/ive</option>
      <option value="conjointe_collaboratrice">Conjoint(e) collaborateur/trice</option>
    </select>
  </div>

  <!-- CC section — only if user is EIRL/EURL AND married/pacsed -->
  {#if canBeCC}
    <div class="mt-3 p-3 bg-purple-950/20 border border-purple-800/20 rounded-lg">
      <label class="flex items-center gap-2 text-xs text-zinc-300 mb-2">
        <input type="checkbox" bind:checked={spouse.is_conjointe_collaboratrice} on:change={debouncedSaveSpouse} />
        Conjoint(e) collaborateur/trice
      </label>
      {#if spouse.is_conjointe_collaboratrice && ccEstimate}
        <div class="grid grid-cols-2 gap-2 mt-2">
          {#each Object.entries(ccEstimate) as [option, data]}
            <button
              class="p-2 rounded-lg text-left border text-xs transition-colors
                {spouse.cc_cotisation_option === option ? 'border-purple-500 bg-purple-900/30' : 'border-zinc-700/30 hover:border-purple-700/30'}"
              on:click={() => { spouse.cc_cotisation_option = option; debouncedSaveSpouse(); }}
            >
              <p class="text-zinc-300 font-medium">{ccLabels[option]}</p>
              <p class="text-purple-400 font-mono">{data.cotisation_mensuelle}€/mois</p>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  <!-- Delete spouse -->
  <button on:click={confirmDeleteSpouse}
    class="text-xs text-zinc-600 hover:text-rose-400 mt-3">
    Retirer le conjoint
  </button>
</Card>
```

**CC availability logic:**
```typescript
$: canBeCC = ['eirl', 'eurl'].includes(profile.status) &&
             ['married', 'pacsed'].includes(spouse?.relationship_type) &&
             spouse != null;
```

### Step 2: Identity page — Spouse career timeline

Below the spouse card, if spouse exists, show a career timeline card identical to the user's but filtered by `?owner=spouse`:

```svelte
{#if spouse}
  <Card title="Parcours de {spouse.first_name || 'conjoint(e)'}" icon="📋" accent="purple">
    <!-- Reuse the same career timeline component but with owner=spouse -->
    <!-- Fetch from GET /api/career?owner=spouse -->
    <!-- Same add/delete pattern as user career -->
  </Card>
{/if}
```

### Step 3: Tax parts prompt

When a spouse is created with `relationship_type` married or pacsed, and current `tax_parts` is 1.0, show an info box:

```svelte
{#if spouse && ['married', 'pacsed'].includes(spouse.relationship_type) && profile.tax_parts < 2}
  <div class="bg-amber-950/20 border border-amber-800/30 rounded-lg p-3 mt-3">
    <p class="text-xs text-amber-300">
      Vos parts fiscales sont à {profile.tax_parts}. Pour un couple {spouse.relationship_type === 'married' ? 'marié' : 'PACSé'}, c'est généralement 2.0 (+0.5/enfant, +1 au 3ème).
      <button on:click={() => updateTaxParts(2)} class="text-amber-200 underline ml-1">Mettre à jour →</button>
    </p>
  </div>
{/if}
```

### Step 4: Runway page — household stats

File: `frontend/src/routes/(app)/runway/+page.svelte`

If spouse exists and has income:
- Stats row labels change: "CA foyer" instead of "CA brut"
- Values include spouse income
- Pension stat shows household pension

### Step 5: Sidebar — household CA

File: `frontend/src/routes/(app)/+layout.svelte` (or wherever sidebar stats live)

If spouse exists, show "CA foyer/mois" instead of "CA/mois" with the combined total.

### Step 6: Data loading

File: `frontend/src/routes/(app)/identity/+page.server.ts`

Add spouse data loading:
```typescript
const spouseRes = await fetch(`${API}/spouse`, { headers });
const spouse = spouseRes.ok ? await spouseRes.json() : null;

let ccEstimate = null;
if (spouse?.is_conjointe_collaboratrice) {
  const ccRes = await fetch(`${API}/spouse/cc-estimate`, { headers });
  ccEstimate = ccRes.ok ? await ccRes.json() : null;
}

let spouseCareer = [];
if (spouse) {
  const scRes = await fetch(`${API}/career?owner=spouse`, { headers });
  spouseCareer = scRes.ok ? await scRes.json() : [];
}
```

### Step 7: i18n keys

Add under `identity.*`:
```json
"spouse": {
  "title": "Conjoint(e)",
  "add": "Ajouter un conjoint",
  "intro": "Ajoutez votre conjoint(e) pour une projection du foyer.",
  "relationship_types": {
    "married": "Marié(e)",
    "pacsed": "PACSé(e)",
    "concubinage": "Concubinage"
  },
  "cc_label": "Conjoint(e) collaborateur/trice",
  "cc_options": {
    "tiers_plafond": "1/3 du plafond SS",
    "moitie_plafond": "1/2 du plafond SS",
    "tiers_revenu": "1/3 du revenu",
    "moitie_revenu": "1/2 du revenu"
  },
  "remove": "Retirer le conjoint",
  "tax_parts_prompt": "Vos parts fiscales sont à {parts}. Pour un couple {type}, c'est généralement 2.0."
}
```

---

## SCOPE BOUNDARY

- DO NOT add a separate login for the spouse.
- DO NOT add spouse-specific savings accounts.
- DO NOT add spouse-specific expense categories.
- DO NOT modify the projection engine — that's TASK-7.8.
- The spouse career timeline reuses the exact same component/pattern as the user's career timeline. DO NOT create a new component.
- Expected change: ~150 lines identity page, ~30 lines runway, ~15 lines sidebar, ~40 lines i18n.

## DONE WHEN

- [ ] "Ajouter un conjoint" button creates spouse via API
- [ ] Spouse edit form saves all fields
- [ ] CC toggle only shown when EIRL/EURL + married/PACSed
- [ ] CC option cards show monthly cotisation from estimate endpoint
- [ ] Tax parts prompt shown when appropriate
- [ ] Spouse career timeline renders below spouse card
- [ ] Runway stats show household totals when spouse exists
- [ ] Sidebar shows "CA foyer/mois"
- [ ] Delete spouse works with confirmation
- [ ] All text via i18n keys
