# TASK-4.4: Runway — Wealth & Income Charts

**Status:** BACKLOG
**Sprint:** 4
**Priority:** P0 (critical)
**Est. effort:** 2 hr
**Dependencies:** TASK-4.2

## Context

Two SVG area charts that tell the story: wealth growing over time, and total income (work + passive + projects) approaching the goal line. No chart library — hand-crafted SVG for full control over styling, keeping the bundle small and matching the prototype's exact aesthetic.

**Prototype reference:** `horizon30.jsx` → `Chart` component. SVG viewBox, polyline for the data, polygon for the gradient fill, optional dashed goal line.

## Requirements

1. Create `frontend/src/lib/components/runway/AreaChart.svelte` — reusable SVG area chart:

   **Props:**
   - `data: Array<{value: number}>` — the Y values
   - `height: number` (default 140)
   - `color: string` (hex, e.g. "#2dd4bf")
   - `goalLine: number | null` — optional horizontal dashed line
   - `startLabel: string`, `endLabel: string` — X-axis labels (e.g. "2026 (40 ans)", "2056 (70 ans)")

   **Rendering:**
   - SVG with viewBox `0 0 400 {height}`, `preserveAspectRatio="none"`, `width="100%"`
   - Compute min/max from data (include goalLine in max if present)
   - Map data points to polyline coordinates: X = `i / (len-1) * 400`, Y = scaled within 7%-92% of height
   - Gradient fill polygon: polyline points + bottom-right + bottom-left
   - Linear gradient: color at 25% opacity → transparent
   - Goal line: horizontal dashed line at the correct Y position, amber (#f59e0b), `stroke-dasharray="6,4"`, opacity 0.6
   - Final point: small circle (r=3) at the last data point

   **No interactivity for MVP** — no hover tooltips, no zoom. Just a clean static chart that updates reactively when the projection store changes.

2. **Wealth chart** (teal accent Card, "Trajectoire patrimoine"):
   - Data: `timeline.map(t => ({value: t.total_wealth}))`
   - Color: `#2dd4bf` (teal-400)
   - No goal line
   - Labels: `"{firstYear} ({currentAge} ans)"` / `"{lastYear} ({targetAge} ans)"`
   - Height: 140

3. **Income chart** (emerald accent Card, "Revenu total mensuel (travail + passif + projets)"):
   - Data: `timeline.map(t => ({value: t.total_monthly_income}))`
   - Color: `#10b981` (emerald-400)
   - Goal line: `profile.monthly_revenue_goal` (if set)
   - Labels: `"{fmt(first.totalMonthly)}/mois"` / `"{fmt(last.totalMonthly)}/mois"`
   - Center label (if goal set): `"Objectif: {fmt(goal)}"` in amber
   - Height: 120

4. Both charts subscribe to the `projectionStore` and re-render when scale changes.

5. **Edge cases:**
   - Empty timeline (birth_date not set) → show placeholder message, not broken chart
   - All values zero → show flat line at bottom
   - Very short timeline (< 5 years) → still renders correctly
   - Negative wealth values → chart extends below zero line

## Technical Approach

### Files to Create
- `frontend/src/lib/components/runway/AreaChart.svelte`
- `frontend/src/routes/(app)/runway/+page.svelte` — add chart sections

### SVG Coordinate Math
```javascript
function toPoints(data, width, height) {
  const vals = data.map(d => d.value);
  const max = Math.max(...vals, goalLine || 0);
  const min = Math.min(...vals, 0);
  const range = max - min || 1;
  return data.map((d, i) => ({
    x: (i / (data.length - 1)) * width,
    y: height - ((d.value - min) / range) * height * 0.85 - height * 0.07,
  }));
}
```

### Gradient Definition
```svelte
<defs>
  <linearGradient id="grad-{id}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color={color} stop-opacity="0.25" />
    <stop offset="100%" stop-color={color} stop-opacity="0" />
  </linearGradient>
</defs>
```

## Acceptance Criteria

- [ ] Wealth chart renders as teal area chart with gradient fill
- [ ] Income chart renders as emerald area chart with gradient fill
- [ ] Goal line (amber dashed) appears on income chart when goal is set
- [ ] Charts update reactively when scale changes
- [ ] Start/end labels render below charts
- [ ] Gradient fills are smooth (no jagged edges)
- [ ] Empty/zero data doesn't break the chart
- [ ] SVG is responsive (scales with container width)
- [ ] Charts render correctly for short timelines (5 years) and long (40 years)
- [ ] No chart library dependency
- [ ] Dark theme: charts look good on zinc-950 background
- [ ] Smoke test: change scale from moderate to pessimistic → both charts visibly change shape
- [ ] LEARNINGS.md updated

## Notes

- Hand-crafted SVG over a chart library because: smaller bundle, full style control, no version conflicts, and the charts are simple (single-series area charts). If we later need interactivity (hover values, zoom), evaluate Layercake (Svelte-native) or Chart.js.
- The gradient fill is what makes the charts look premium vs a bare line. Get the opacity right — too opaque looks heavy, too transparent is invisible on the dark background.
- Each chart needs a unique gradient ID to avoid SVG rendering conflicts when both are on the same page. Use the color hex as part of the ID: `id="grad-2dd4bf"`.
