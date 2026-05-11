# TASK-7.10: Income Events in Projets

**Status:** TODO
**Sprint:** 7
**Priority:** P2 (medium)
**Est. effort:** 2 hr
**Dependencies:** TASK-7.5

---

## Context

The Projets page has investments, life events, and status change. This task adds "Projets de revenus" — future income sources (product launches, company sales, dividends, new contracts). These are income sources from TASK-7.5 with `start_date` in the future or `frequency = one_time`. Same underlying data, different view.

---

## Step-by-Step Instructions

### Step 1: Add section to Projets page

File: `frontend/src/routes/(app)/projects/+page.svelte`

Add a new section (sky accent) between "Événements de vie" and "Changement de statut":

```svelte
<Card title="Projets de revenus" icon="💰" accent="sky">
  <p class="text-xs text-zinc-500 mb-3">
    Sources de revenus futures — lancement de produit, vente d'entreprise, dividendes, nouveau contrat.
  </p>

  {#each futureIncomeSources as source (source.id)}
    <div class="p-3 bg-zinc-900/60 border border-zinc-700/30 rounded-lg mb-2">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-xs font-medium text-zinc-200">{source.label}</span>
        <span class="text-[9px] px-1.5 py-0.5 rounded-full bg-sky-900/40 text-sky-300">
          {sourceTypeLabels[source.source_type] || source.source_type}
        </span>
        <span class="text-[9px] {confidenceBadge[source.confidence]}">
          {source.confidence === 'high' ? '🟢' : source.confidence === 'medium' ? '🟡' : '🔴'}
        </span>
      </div>
      <div class="flex items-center gap-3 text-[10px] text-zinc-500">
        <span class="font-mono text-sky-400">
          {parseFloat(source.amount).toLocaleString('fr-FR')}€
          {source.frequency === 'one_time' ? '' : source.frequency === 'monthly' ? '/mois' : '/an'}
        </span>
        {#if source.start_date}
          <span>À partir de {source.start_date.substring(0, 7)}</span>
        {/if}
        {#if source.end_date}
          <span>→ {source.end_date.substring(0, 7)}</span>
        {/if}
      </div>
      {#if source.notes}
        <p class="text-[10px] text-zinc-600 mt-1 italic">{source.notes}</p>
      {/if}
      <button on:click={() => deleteIncomeSource(source.id)}
        class="text-[10px] text-zinc-600 hover:text-rose-400 mt-1">Supprimer</button>
    </div>
  {/each}

  <button on:click={addFutureIncomeSource}
    class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-sky-700/50 mt-1">
    + Ajouter un projet de revenu
  </button>
</Card>
```

### Step 2: Data filtering

Future income sources = income sources where:
- `start_date` is in the future, OR
- `frequency = "one_time"`

```typescript
$: futureIncomeSources = allIncomeSources.filter(s =>
  (s.start_date && new Date(s.start_date) > new Date()) ||
  s.frequency === 'one_time'
);
```

### Step 3: Add/delete operations

```typescript
async function addFutureIncomeSource() {
  const nextYear = new Date().getFullYear() + 1;
  const source = await api.post('/income-sources', {
    label: 'Nouveau projet',
    source_type: 'other',
    amount: 0,
    frequency: 'one_time',
    start_date: `${nextYear}-01-01`,
    confidence: 'medium',
    is_ae_revenue: true,
  });
  if (source) allIncomeSources = [...allIncomeSources, source];
}

async function deleteIncomeSource(id: string) {
  await api.delete(`/income-sources/${id}`);
  allIncomeSources = allIncomeSources.filter(s => s.id !== id);
}
```

### Step 4: Load data in page.server.ts

File: `frontend/src/routes/(app)/projects/+page.server.ts`

Add income sources to the page data:
```typescript
const sourcesRes = await fetch(`${API}/income-sources`, { headers });
const incomeSources = sourcesRes.ok ? await sourcesRes.json() : [];
return { ...existingData, incomeSources };
```

### Step 5: i18n keys

Add under `projects.*`:
```json
"income": {
  "title": "Projets de revenus",
  "description": "Sources de revenus futures — lancement de produit, vente d'entreprise, dividendes, nouveau contrat.",
  "add_button": "Ajouter un projet de revenu",
  "source_types": {
    "client": "Client",
    "product": "Produit",
    "dividends": "Dividendes",
    "sale": "Vente",
    "rental": "Locatif",
    "other": "Autre"
  }
}
```

---

## SCOPE BOUNDARY

- DO NOT add inline editing on this page. Sources are edited on the Revenue page (TASK-7.6).
- DO NOT add impact preview calculations — that's a future enhancement.
- DO NOT duplicate income source data. This is a filtered VIEW of the same `income_sources` table.
- Expected change: ~80 lines svelte, ~10 lines server, ~15 lines i18n.

## DONE WHEN

- [ ] "Projets de revenus" section visible on Projets page
- [ ] Shows income sources with future start_date or one_time frequency
- [ ] Source type badges and confidence indicators displayed
- [ ] Can add a new future income source (pre-filled with next year)
- [ ] Can delete a source
- [ ] Sources created here also appear on Revenue page (same data)
- [ ] All text via i18n keys
