# TASK-7.14: Confidence Bands on Charts

**Status:** TODO
**Sprint:** 7
**Priority:** P2 (medium)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-7.5

---

## Context

The Runway page shows three discrete scenario lines (optimistic/moderate/pessimistic) toggled by a selector. The user sees one line at a time. A confidence band — a shaded area between the optimistic and pessimistic curves, with the moderate line in the middle — communicates uncertainty better. Income sources with low confidence (from TASK-7.5) widen the band.

---

## Step-by-Step Instructions

### Step 1: Fetch all 3 projections

File: `frontend/src/routes/(app)/runway/+page.server.ts`

Currently the page fetches one projection for the selected scale. Instead, fetch all 3:

```typescript
const [optRes, modRes, pesRes] = await Promise.all([
  fetch(`${API}/projection?scale=optimistic`, { headers }),
  fetch(`${API}/projection?scale=moderate`, { headers }),
  fetch(`${API}/projection?scale=pessimistic`, { headers }),
]);

return {
  projections: {
    optimistic: await optRes.json(),
    moderate: await modRes.json(),
    pessimistic: await pesRes.json(),
  },
  selectedScale: scale,
  // ... existing data
};
```

### Step 2: Compute confidence band widening from income sources

If the user has income sources with `confidence = "low"`, widen the pessimistic band further. Simple approach: for each low-confidence source contributing >10% of income, reduce the pessimistic wealth trajectory by an additional 5%.

```typescript
function adjustForConfidence(pessTimeline: any[], sources: any[]): any[] {
  const lowConfidencePct = sources
    .filter(s => s.confidence === 'low' && s.is_active)
    .reduce((sum, s) => sum + parseFloat(s.amount), 0);
  const totalIncome = sources
    .filter(s => s.is_active && s.frequency === 'monthly')
    .reduce((sum, s) => sum + parseFloat(s.amount), 0);
  
  if (totalIncome === 0) return pessTimeline;
  
  const uncertaintyFactor = Math.min(0.15, (lowConfidencePct / totalIncome) * 0.2);
  
  return pessTimeline.map(t => ({
    ...t,
    total_wealth: String(parseFloat(t.total_wealth) * (1 - uncertaintyFactor)),
  }));
}
```

### Step 3: Render confidence band on wealth chart

File: `frontend/src/routes/(app)/runway/+page.svelte`

Replace the single-line SVG chart with a band chart:

```svelte
{@const optData = projections.optimistic.timeline.map(t => ({ year: t.year, v: parseFloat(t.total_wealth) }))}
{@const modData = projections.moderate.timeline.map(t => ({ year: t.year, v: parseFloat(t.total_wealth) }))}
{@const pesData = adjustedPessimistic.map(t => ({ year: t.year, v: parseFloat(t.total_wealth) }))}

<svg viewBox="0 0 400 120" class="w-full" preserveAspectRatio="none" style="height:120px">
  <!-- Confidence band (area between optimistic and pessimistic) -->
  <polygon points="{bandPolygon}" fill="url(#bandGradient)" opacity="0.15" />
  
  <!-- Pessimistic line -->
  <polyline points="{pesLine}" fill="none" stroke="#f43f5e" stroke-width="1" stroke-dasharray="4,3" opacity="0.4" />
  
  <!-- Optimistic line -->
  <polyline points="{optLine}" fill="none" stroke="#10b981" stroke-width="1" stroke-dasharray="4,3" opacity="0.4" />
  
  <!-- Moderate line (main) -->
  <polyline points="{modLine}" fill="none" stroke="#2dd4bf" stroke-width="2" />
  
  <!-- Goal line -->
  {#if goalLineY != null}
    <line x1="0" y1={goalLineY} x2="400" y2={goalLineY} stroke="#f59e0b" stroke-width="1" stroke-dasharray="6,4" opacity="0.6" />
  {/if}
  
  <defs>
    <linearGradient id="bandGradient" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#10b981" stop-opacity="0.3" />
      <stop offset="100%" stop-color="#f43f5e" stop-opacity="0.1" />
    </linearGradient>
  </defs>
</svg>
```

**Band polygon computation:**
The band is formed by the optimistic curve going left-to-right across the top, then the pessimistic curve going right-to-left across the bottom:

```typescript
$: bandPolygon = (() => {
  const w = 400, h = 120;
  const allVals = [...optData, ...pesData].map(d => d.v);
  const max = Math.max(...allVals, goalLine || 0);
  const min = Math.min(...allVals, 0);
  const range = max - min || 1;
  
  const toY = (v: number) => h - ((v - min) / range) * h * 0.85 - h * 0.07;
  const toX = (i: number, total: number) => (i / (total - 1)) * w;
  
  const topPts = optData.map((d, i) => `${toX(i, optData.length)},${toY(d.v)}`).join(' ');
  const bottomPts = pesData.map((d, i) => `${toX(i, pesData.length)},${toY(d.v)}`).reverse().join(' ');
  
  return `${topPts} ${bottomPts}`;
})();
```

### Step 4: Do the same for income chart

Apply the same band pattern to the income chart (if it exists as a separate SVG).

### Step 5: Keep scale selector functional

The scale selector still exists but now controls which line is "primary" (thicker, labeled). All three are always visible. The band is always shown.

---

## SCOPE BOUNDARY

- DO NOT add hover tooltips to the chart bands. Browser-native `title` is fine.
- DO NOT use a charting library (recharts, chart.js). This is raw SVG — keep it consistent with existing charts.
- DO NOT add animation to the band transitions.
- DO NOT add a Monte Carlo simulation. The band is deterministic (3 scenarios + confidence adjustment).
- The confidence adjustment is a simple multiplicative factor. DO NOT model probability distributions.
- Expected: ~50 lines server, ~80 lines chart SVG.

## DONE WHEN

- [ ] All 3 projections fetched in parallel
- [ ] Shaded band visible between optimistic and pessimistic curves
- [ ] Moderate line rendered as primary (thicker)
- [ ] Optimistic and pessimistic as dashed, lighter lines
- [ ] Low-confidence income sources widen the pessimistic band
- [ ] Scale selector still works (changes primary line emphasis)
- [ ] Goal line still visible
- [ ] Both wealth and income charts have bands
