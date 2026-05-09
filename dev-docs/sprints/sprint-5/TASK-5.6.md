# TASK-5.6: Chart Polish & Interactivity

**Status:** TODO
**Sprint:** 5
**Priority:** P1 (high)
**Est. effort:** 2 hr
**Dependencies:** TASK-4.3

## Context

The current SVG area charts communicate trend but not magnitude. For a financial planning tool, the exact numbers matter — a user needs to know that their wealth is 65.7k€ in 2036, not just "the line is going up." The charts need Y-axis labels, grid lines, hover/touch tooltips, and better visual communication of key moments (retirement, milestones, goal line).

## Requirements

### Chart Enhancements (apply to both Wealth Trajectory and Income charts)

1. **Y-axis labels:**
   - 4–6 labels on the left edge, evenly spaced
   - Format: abbreviated (e.g., "50k€", "100k€", "150k€")
   - Font: 10px JetBrains Mono, zinc-500
   - Subtle horizontal grid lines at each label (zinc-800/20, dashed)

2. **X-axis labels:**
   - Show at least: first year, last year, and 2–3 intermediate points
   - Format: "2030" or "2030 (44 ans)"
   - Font: 10px JetBrains Mono, zinc-500

3. **Hover/touch tooltips:**
   - On mouseover (desktop) or tap (mobile), show a vertical crosshair line
   - Tooltip box near the cursor showing:
     - Year and age
     - Exact value (formatted: "67 234€")
     - For income chart: breakdown (travail + passif + projets)
   - Tooltip styling: zinc-800 bg, zinc-100 text, rounded, subtle shadow
   - Snap to nearest data point (not continuous)

4. **Goal line** (income chart only):
   - Horizontal dashed line at the goal value
   - Label on the right edge: "Objectif: 4 000€/mois"
   - Color: amber (#f59e0b), dashed stroke
   - If goal is reached, highlight the intersection point

5. **Retirement marker** (both charts, needed for TASK-5.2):
   - Vertical dashed line at retirement age
   - Label: "Retraite (70 ans)"
   - Color: zinc-500, subtle
   - Area to the right of the line could have a slightly different fill opacity

6. **Milestone markers** (wealth chart):
   - Small dots on the curve at 100k€, 250k€, 500k€, 1M€ thresholds
   - Color matches the milestone colors from MilestoneTimeline
   - No labels on the chart itself (too cluttered) — the timeline below handles that

7. **Area fill gradient:**
   - Keep the current gradient but ensure it starts from the bottom of the chart area, not from zero
   - For post-retirement drawdown (TASK-5.2): use a different gradient (rose-tinted) when wealth is declining

### Technical Approach

8. **Refactor `AreaChart.svelte`** to accept configuration:
   ```svelte
   <AreaChart
     data={timeline}
     xKey="year"
     yKey="total_wealth"
     formatY={fmtK}
     formatTooltip={formatWealthTooltip}
     showGrid={true}
     markers={milestoneMarkers}
     verticalLines={[{ x: retirementYear, label: "Retraite" }]}
     horizontalLines={[]}
     gradientId="wealth-gradient"
     color="teal"
   />
   ```

9. **Responsive sizing:**
   - Charts should fill container width
   - Height: 280px desktop, 200px mobile
   - Tooltip positioning should not overflow the chart container
   - Touch targets for tooltips should be at least 44px

10. **Performance:**
    - Use `requestAnimationFrame` for tooltip positioning
    - Debounce mousemove events (16ms — one frame)
    - Don't re-render the entire SVG on hover — use a separate overlay layer

## Acceptance Criteria

- [ ] Y-axis labels render with correct values and formatting
- [ ] X-axis labels show year and optionally age
- [ ] Grid lines render subtly without overwhelming the chart
- [ ] Hover tooltip shows exact values for the nearest data point
- [ ] Touch tooltip works on mobile (tap to show, tap elsewhere to dismiss)
- [ ] Goal line renders on income chart with label
- [ ] Retirement age marker renders as vertical dashed line
- [ ] Area gradient looks clean from zero baseline
- [ ] Charts remain performant with 30+ data points
- [ ] No layout shift when tooltips appear/disappear
- [ ] LEARNINGS.md updated

## Notes

- Keep the charts simple and clean. The temptation is to add too many features. Grid + axes + tooltip is the priority. Fancy animations are secondary.
- The SVG approach (no chart library) is the right call for MVP — it keeps the bundle small and gives full control over styling. If charts become significantly more complex in future sprints, consider a lightweight library.
- Test tooltip positioning at chart edges — the tooltip should flip to the other side of the crosshair when near the right or top edge.
