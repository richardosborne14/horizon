# TASK-7.6: Revenue Page Overhaul — Frontend

**Status:** TODO
**Sprint:** 7
**Priority:** P1 (high)
**Est. effort:** 3 hr
**Dependencies:** TASK-7.5

---

## Context

The current Revenue page has a single CA input, growth presets, 5-year preview, and CESU/charity tax breaks. This task replaces the single CA input with a multi-source income manager using the `income_sources` API from TASK-7.5. Growth presets and tax breaks stay. The 5-year preview becomes a 10-year timeline showing when sources start, end, and overlap.

---

## Step-by-Step Instructions

### Step 1: Update page.server.ts

File: `frontend/src/routes/(app)/revenue/+page.server.ts`

Add data loading for income sources:

```typescript
const [profileRes, growthRes, rateRes, sourcesRes] = await Promise.all([
  fetch(`${API}/profile`, { headers }),
  fetch(`${API}/constants/growth-presets`, { headers }),
  fetch(`${API}/rates/ae-schedule?type=${profile.ae_activity_type}`, { headers }),
  fetch(`${API}/income-sources`, { headers }),
]);
// ... parse all responses
return {
  profile,
  growthPresets,
  rateSchedule,
  incomeSources: sources,
  // ... existing data
};
```

### Step 2: Income sources list card

Replace the single CA input card with a new "Sources de revenus" card (teal accent).

**Collapsed source row:**
```svelte
<div class="flex items-center gap-2 p-2 bg-zinc-900/60 border border-zinc-700/30 rounded-lg">
  <span class="w-2 h-2 rounded-full {source.earner === 'user' ? 'bg-teal-500' : 'bg-purple-500'}"></span>
  <span class="text-xs text-zinc-300 flex-1 truncate">{source.label}</span>
  <span class="text-xs font-mono text-teal-400">
    {parseFloat(source.amount).toLocaleString('fr-FR')}€
    {source.frequency === 'monthly' ? '/mois' : source.frequency === 'annual' ? '/an' : ''}
  </span>
  <span class="text-[9px] px-1.5 py-0.5 rounded-full {confidenceColors[source.confidence]}">
    {source.confidence === 'high' ? '🟢' : source.confidence === 'medium' ? '🟡' : '🔴'}
  </span>
  {#if source.end_date}
    <span class="text-[10px] text-zinc-500">→ {source.end_date.substring(0, 7)}</span>
  {/if}
  <button on:click={() => toggleExpand(source.id)} class="text-zinc-500 text-xs">
    {expanded === source.id ? '▲' : '▼'}
  </button>
</div>
```

**Expanded edit form** (shown when `expanded === source.id`):

Fields: label (text), source_type (select), amount (number), frequency (select: mensuel/annuel/ponctuel), start_date (date), end_date (date), confidence (select), annual_growth_rate (number, %), is_ae_revenue (checkbox), notes (text).

Auto-save on change (debounce 800ms) via `PUT /api/income-sources/{id}`.

### Step 3: Source type quick-add presets

When clicking "+ Ajouter une source", show a small preset picker:

| Preset | Label | Type | Frequency | Confidence | AE Revenue |
|--------|-------|------|-----------|------------|------------|
| Client régulier | "Nouveau client" | client | monthly | high | true |
| Produit/SaaS | "Produit" | product | monthly | medium | true |
| Mission ponctuelle | "Mission" | client | one_time | high | true |
| Dividendes | "Dividendes" | dividends | annual | medium | false |
| Vente d'actif | "Vente" | sale | one_time | medium | false |
| Salaire (conjoint) | "Salaire" | salary | monthly | high | false |

Clicking a preset creates the source via `POST /api/income-sources` with the preset values, then opens the expanded form for editing.

### Step 4: Revenue timeline preview

Replace the 5-year CA preview with a 10-year horizontal stacked bar visualization. This is a simple SVG or HTML element — NOT a chart library.

For each of the next 10 years, compute which sources are active and sum their monthly contribution:

```typescript
function computeTimeline(sources: any[], currentYear: number): Array<{year: number, segments: Array<{label: string, amount: number, color: string}>}> {
  const timeline = [];
  for (let y = currentYear; y < currentYear + 10; y++) {
    const yearStart = new Date(y, 0, 1);
    const yearEnd = new Date(y, 11, 31);
    const segments = sources
      .filter(s => s.is_active)
      .filter(s => !s.start_date || new Date(s.start_date) <= yearEnd)
      .filter(s => !s.end_date || new Date(s.end_date) >= yearStart)
      .filter(s => s.frequency !== 'one_time')
      .map(s => ({
        label: s.label,
        amount: s.frequency === 'annual' ? parseFloat(s.amount) / 12 : parseFloat(s.amount),
        color: s.earner === 'user' ? 'teal' : 'purple',
      }));
    timeline.push({ year: y, segments });
  }
  return timeline;
}
```

Render as stacked horizontal bars:
```svelte
<div class="space-y-1 mt-3">
  {#each timeline as yearData}
    <div class="flex items-center gap-2">
      <span class="text-[10px] text-zinc-500 w-10 font-mono">{yearData.year}</span>
      <div class="flex-1 flex h-4 rounded overflow-hidden bg-zinc-800">
        {#each yearData.segments as seg}
          <div
            class="h-full {seg.color === 'teal' ? 'bg-teal-600/60' : 'bg-purple-600/60'}"
            style="width: {(seg.amount / maxMonthly) * 100}%"
            title="{seg.label}: {seg.amount.toLocaleString('fr-FR')}€/mois"
          ></div>
        {/each}
      </div>
      <span class="text-[10px] font-mono text-zinc-400 w-16 text-right">
        {yearData.segments.reduce((s, x) => s + x.amount, 0).toLocaleString('fr-FR')}€
      </span>
    </div>
  {/each}
</div>
```

### Step 5: Stats row update

Update the stats row to compute from income sources instead of the single CA field:

- **CA brut mensuel (teal):** sum of active user AE sources (monthly + annual/12)
- **Cotisations (rose):** CA × AE rate
- **Net (emerald):** CA − cotisations

If spouse sources exist, optionally show household totals.

### Step 6: Keep CESU/charity unchanged

The CESU and charity tax break cards stay exactly as they are. No changes needed.

---

## SCOPE BOUNDARY

- DO NOT add drag-and-drop reordering of sources.
- DO NOT add income source analytics or charts beyond the stacked bar timeline.
- DO NOT modify the growth preset selector logic — it stays as default for sources without a custom rate.
- DO NOT add source-level profit/loss calculations — that's the projection engine's job.
- The timeline is a simple visualization, NOT an interactive chart. No hover tooltips beyond browser-native `title`.
- Expected change: ~200 lines in page.svelte, ~20 lines in page.server.ts.

## DONE WHEN

- [ ] Income sources list replaces single CA input
- [ ] Collapsed rows show label, amount, confidence, end date
- [ ] Expanded form allows editing all source fields
- [ ] Quick-add presets create sources with sensible defaults
- [ ] 10-year timeline renders stacked bars per year
- [ ] Timeline visually shows gaps when sources end
- [ ] Stats row computes from active sources
- [ ] Spouse sources shown in purple (if spouse exists)
- [ ] Auto-save with 800ms debounce
- [ ] CESU/charity unchanged
- [ ] All text via i18n keys
