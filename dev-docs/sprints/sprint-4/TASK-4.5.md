# TASK-4.5: Runway — Milestones & Projection Table

**Status:** BACKLOG
**Sprint:** 4
**Priority:** P1 (high)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-4.2

## Context

Two components that add detail to the charts: the milestone timeline (a visual celebration of wealth thresholds) and the detailed projection table (the spreadsheet for people who want to see every number). Both consume the projection store.

**Prototype reference:** `horizon30.jsx` → `Runway` → milestones (vertical timeline with colored dots) and table (every 5th year, colored columns).

## Requirements

### Milestones Timeline

1. Create `frontend/src/lib/components/runway/MilestoneTimeline.svelte`:
   - Data: `projection.summary.milestones` array
   - Vertical timeline with a thin line (`w-px bg-zinc-800`) on the left
   - Each milestone: colored dot (circle with border, inner fill) + bold label + year/age text
   - Colors per threshold:
     - 100k€ → teal (#22d3ee)
     - 250k€ → purple (#a78bfa)
     - 500k€ → amber (#f59e0b)
     - 1M€ → emerald (#10b981)
   - Card wrapper: "Jalons" title

2. **Empty state:** If no milestones (wealth never reaches 100k), show: "Aucun jalon atteint sur cette période. Augmentez votre épargne mensuelle pour voir les jalons apparaître."

### Projection Table

3. Create `frontend/src/lib/components/runway/ProjectionTable.svelte`:
   - Data: `projection.timeline`, filtered to every 5th year + final year
   - Columns: An, Âge, CA brut, Cotis., Cotis.%, Vie, Enfants, Projets, Net, Patrimoine, Passif/mois
   - Styling:
     - Header: 9px uppercase zinc-500, border-bottom zinc-800
     - Rows: 11px font-mono, border-top zinc-800/30, hover bg-zinc-800/10
     - Color coding: teal for positive net, rose for negative, emerald for passive income, amber for cotisations, purple for kid expenses
     - All numbers right-aligned except year (left)
     - Use `fmtK()` for large values (e.g. "42k€" not "42 000 €")
   - Card wrapper: "Projection détaillée" title

4. **Responsive:** Horizontal scroll on mobile (`overflow-x-auto`). The table is necessarily wide (11 columns).

5. **Row filtering:** Show years at indices 0, 5, 10, 15, 20, 25, 29 (or whatever matches every 5th year + the final year). Use: `timeline.filter((_, i) => i % 5 === 0 || i === timeline.length - 1)`

6. **Special cells:**
   - Kid expenses: show "—" if zero (no kids or kids aged out)
   - Projects: show `+{income}` if income > 0, `-{expense}` if expense > 0, "—" if neither
   - Cotis.%: show the AE rate as percentage (useful to see it climbing over time)

## Technical Approach

### Files to Create
- `frontend/src/lib/components/runway/MilestoneTimeline.svelte`
- `frontend/src/lib/components/runway/ProjectionTable.svelte`
- `frontend/src/routes/(app)/runway/+page.svelte` — add both components

### Milestone Dot Pattern (from prototype)
```svelte
{#each milestones as m}
  <div class="flex items-center gap-3 py-2">
    <div class="w-4 h-4 rounded-full border-2 bg-zinc-950 z-10 flex items-center justify-center"
         style="border-color: {m.color}">
      <div class="w-1.5 h-1.5 rounded-full" style="background-color: {m.color}" />
    </div>
    <span class="text-sm font-mono font-bold" style="color: {m.color}">{m.label}</span>
    <span class="text-xs text-zinc-500">→ {m.year} (à {m.age} ans)</span>
  </div>
{/each}
```

### Table Row Pattern
```svelte
{#each filteredTimeline as t}
  <tr class="border-t border-zinc-800/30 hover:bg-zinc-800/10">
    <td class="py-1.5 font-mono text-zinc-400">{t.year}</td>
    <td class="font-mono text-zinc-300 text-right">{t.age}</td>
    <td class="font-mono text-zinc-300 text-right">{fmtK(t.gross_annual)}</td>
    <td class="font-mono text-rose-400/70 text-right">{fmtK(t.charges)}</td>
    <td class="font-mono text-rose-400/50 text-right">{fmtPct(t.ae_rate)}</td>
    <td class="font-mono text-amber-400/70 text-right">{fmtK(t.base_expenses)}</td>
    <td class="font-mono text-purple-400/70 text-right">{t.kid_expenses > 0 ? fmtK(t.kid_expenses) : '—'}</td>
    <td class="font-mono text-sky-400/70 text-right">{projectCell(t)}</td>
    <td class="font-mono text-right font-medium {t.net_annual >= 0 ? 'text-teal-400' : 'text-rose-400'}">
      {fmtK(t.net_annual)}
    </td>
    <td class="font-mono font-bold text-white text-right">{fmtK(t.total_wealth)}</td>
    <td class="font-mono text-emerald-400 text-right">{fmt(t.passive_monthly)}</td>
  </tr>
{/each}
```

## Acceptance Criteria

- [ ] Milestones render with correct colors at correct wealth thresholds
- [ ] Milestones update when scale changes
- [ ] Empty milestones shows helpful message
- [ ] Table shows every 5th year + final year
- [ ] Table columns color-coded correctly
- [ ] Kid expenses show "—" when zero
- [ ] Cotisation % column shows rate increasing over time
- [ ] Table scrolls horizontally on mobile
- [ ] All numbers formatted with `fmtK` (compact) and right-aligned
- [ ] Both components react to projection store changes
- [ ] Dark theme matches prototype
- [ ] LEARNINGS.md updated

## Notes

- The milestone timeline is a psychological motivator. Seeing "100k€ → 2035 (à 49 ans)" makes the abstract feel achievable. Get the visual right — the colored dots should pop against the dark background.
- The table is for the analytically-minded user who wants to see the raw numbers. Most users will glance at it; some will study it. The compact `fmtK` formatting keeps it scannable.
- The Cotis.% column is unique to Horizon 30 — it shows the user that their AE rate isn't flat. Seeing 26.2% in 2026 and 29.5% in 2035 is a powerful "the system is squeezing you" moment.
