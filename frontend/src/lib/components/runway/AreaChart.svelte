<script lang="ts">
  /**
   * Reusable SVG area chart — hand-crafted, no library dependency.
   * Sprint 5.6 polish: Y-axis labels, grid lines, X-axis labels, hover tooltips.
   * 
   * Used for wealth trajectory and income trajectory on the Runway page.
   * Props:
   *   data: Array of { value: number, isRetirement?: boolean } 
   *   height: chart SVG viewBox height
   *   color: line/fill color
   *   goalLine: horizontal goal line value (null = none)
   *   startLabel/endLabel: axis labels below the chart
   *   formatY: formatter for Y-axis values (e.g., fmtK)
   *   showRetirementMarker: render vertical dashed line at retirement transition
   *   retirementIndex: index in data where retirement starts
   */
  import { fmt, fmtK } from '$lib/utils/format';

  export let data: Array<{ value: number; isRetirement?: boolean }> = [];
  export let height = 200;
  export let color = '#2dd4bf';
  export let goalLine: number | null = null;
  export let startLabel = '';
  export let endLabel = '';
  export let formatY: (v: number) => string = (v) => fmtK(String(v));
  export let showRetirementMarker: boolean = false;
  export let retirementIndex: number = -1;

  const WIDTH = 400;
  const MARGIN_LEFT = 50;
  const MARGIN_RIGHT = 10;
  const MARGIN_TOP = 8;
  const MARGIN_BOTTOM = 18;
  const CHART_WIDTH = WIDTH - MARGIN_LEFT - MARGIN_RIGHT;
  const CHART_HEIGHT = height - MARGIN_TOP - MARGIN_BOTTOM;

  let gradientId = '';
  $: gradientId = `grad-${color.replace('#', '')}`;

  $: points = computePoints(data, goalLine);
  $: goalY = computeGoalY(goalLine, data);
  $: yLabels = computeYLabels(data, goalLine);
  $: xLabels = computeXLabels(data);
  $: retirementX = showRetirementMarker && retirementIndex >= 0 && retirementIndex < data.length
    ? MARGIN_LEFT + (retirementIndex / Math.max(data.length - 1, 1)) * CHART_WIDTH
    : null;

  // Hover state
  let hoverIndex: number | null = null;
  let hoverX: number = 0;
  let hoverY: number = 0;

  function computePoints(
    vals: Array<{ value: number }>,
    goal: number | null
  ): Array<{ x: number; y: number }> {
    if (!vals.length) return [];
    const nums = vals.map((d) => d.value);
    let max = Math.max(...nums);
    let min = Math.min(...nums);
    if (goal !== null) max = Math.max(max, goal);
    if (min > 0) min = 0;
    const range = max - min || 1;

    return vals.map((d, i) => ({
      x: MARGIN_LEFT + (i / Math.max(vals.length - 1, 1)) * CHART_WIDTH,
      y: MARGIN_TOP + CHART_HEIGHT - ((d.value - min) / range) * CHART_HEIGHT
    }));
  }

  function computeGoalY(goal: number | null, vals: Array<{ value: number }>): number | null {
    if (goal === null || !vals.length) return null;
    const nums = vals.map((d) => d.value);
    let max = Math.max(...nums);
    let min = Math.min(...nums);
    if (max < goal) max = goal;
    if (min > 0) min = 0;
    const range = max - min || 1;
    return MARGIN_TOP + CHART_HEIGHT - ((goal - min) / range) * CHART_HEIGHT;
  }

  function computeYLabels(
    vals: Array<{ value: number }>,
    goal: number | null
  ): Array<{ value: number; y: number; label: string }> {
    if (!vals.length) return [];
    const nums = vals.map((d) => d.value);
    let max = Math.max(...nums);
    let min = Math.min(...nums);
    if (goal !== null) max = Math.max(max, goal);
    if (min > 0) min = 0;
    const range = max - min || 1;
    const count = 4;
    const result: Array<{ value: number; y: number; label: string }> = [];
    for (let i = 0; i <= count; i++) {
      const value = min + (range * i) / count;
      result.push({
        value,
        y: MARGIN_TOP + CHART_HEIGHT - (value - min) / range * CHART_HEIGHT,
        label: formatY(value)
      });
    }
    return result;
  }

  function computeXLabels(vals: Array<{ value: number; year?: number }>): Array<{ x: number; label: string }> {
    if (vals.length <= 1) return [];
    const result: Array<{ x: number; label: string }> = [];
    const indices = [0, Math.floor(vals.length / 2), vals.length - 1];
    for (const idx of indices) {
      const yr = vals[idx]?.year;
      result.push({
        x: MARGIN_LEFT + (idx / Math.max(vals.length - 1, 1)) * CHART_WIDTH,
        label: yr != null ? String(yr) : String(idx)
      });
    }
    return result;
  }

  function onMouseMove(e: MouseEvent) {
    if (!points.length || !data.length) return;
    const svg = e.currentTarget as SVGSVGElement;
    const rect = svg.getBoundingClientRect();
    const scaleX = WIDTH / rect.width;
    const mouseX = (e.clientX - rect.left) * scaleX;
    // Find nearest data point
    let best = 0;
    let bestDist = Infinity;
    for (let i = 0; i < points.length; i++) {
      const dist = Math.abs(points[i].x - mouseX);
      if (dist < bestDist) {
        bestDist = dist;
        best = i;
      }
    }
    hoverIndex = best;
    hoverX = points[best].x;
    hoverY = points[best].y;
  }

  function onMouseLeave() {
    hoverIndex = null;
  }

  $: polylinePoints = points.map((p) => `${p.x},${p.y}`).join(' ');
  $: fillPoints = points.length > 0
    ? polylinePoints + ` ${MARGIN_LEFT + CHART_WIDTH},${height - MARGIN_BOTTOM} ${MARGIN_LEFT},${height - MARGIN_BOTTOM}`
    : '';
</script>

<div class="relative">
  <svg
    viewBox={`0 0 ${WIDTH} ${height}`}
    preserveAspectRatio="xMidYMid meet"
    width="100%"
    class="overflow-visible"
    on:mousemove={onMouseMove}
    on:mouseleave={onMouseLeave}
  >
    <defs>
      <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color={color} stop-opacity="0.25" />
        <stop offset="100%" stop-color={color} stop-opacity="0" />
      </linearGradient>
    </defs>

    <!-- Grid lines -->
    {#each yLabels as yl}
      <line x1={MARGIN_LEFT} y1={yl.y} x2={MARGIN_LEFT + CHART_WIDTH} y2={yl.y}
        stroke="#3f3f46" stroke-width="0.5" stroke-dasharray="4,4" opacity="0.5" />
    {/each}

    <!-- Area fill -->
    {#if points.length > 0}
      <polygon points={fillPoints} fill={`url(#${gradientId})`} />
      <!-- Line -->
      <polyline points={polylinePoints} fill="none" stroke={color}
        stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
      <!-- Final point -->
      {#if points.length > 1}
        <circle cx={points[points.length - 1].x} cy={points[points.length - 1].y}
          r="3" fill={color}></circle>
      {/if}
    {/if}

    <!-- Goal line -->
    {#if goalLine !== null && goalY !== null}
      <line x1={MARGIN_LEFT} y1={goalY} x2={MARGIN_LEFT + CHART_WIDTH} y2={goalY}
        stroke="#f59e0b" stroke-width="1" stroke-dasharray="6,4" opacity="0.6" />
      <text x={MARGIN_LEFT + CHART_WIDTH + 2} y={goalY + 3} fill="#f59e0b"
        font-size="8" font-family="JetBrains Mono, monospace">Obj.</text>
    {/if}

    <!-- Retirement marker -->
    {#if retirementX !== null}
      <line x1={retirementX} y1={MARGIN_TOP} x2={retirementX} y2={height - MARGIN_BOTTOM}
        stroke="#71717a" stroke-width="1" stroke-dasharray="4,4" opacity="0.5" />
      <text x={retirementX + 3} y={MARGIN_TOP + 10} fill="#71717a"
        font-size="7" font-family="Inter, sans-serif">Retraite</text>
    {/if}

    <!-- Y-axis labels -->
    {#each yLabels as yl}
      <text x={MARGIN_LEFT - 4} y={yl.y + 3} fill="#71717a"
        font-size="7" font-family="JetBrains Mono, monospace" text-anchor="end">{yl.label}</text>
    {/each}

    <!-- X-axis labels -->
    {#each xLabels as xl}
      <text x={xl.x} y={height - 3} fill="#71717a"
        font-size="7" font-family="JetBrains Mono, monospace" text-anchor="middle">{xl.label}</text>
    {/each}

    <!-- Hover crosshair -->
    {#if hoverIndex !== null}
      <line x1={hoverX} y1={MARGIN_TOP} x2={hoverX} y2={height - MARGIN_BOTTOM}
        stroke="#a1a1aa" stroke-width="0.5" opacity="0.6" />
      <circle cx={hoverX} cy={hoverY} r="4" fill={color} stroke="#fff" stroke-width="1.5" />
      <!-- Tooltip box -->
      <rect x={hoverX + 6} y={hoverY - 14} width={60} height={16} rx={3}
        fill="#27272a" stroke="#3f3f46" stroke-width="0.5" opacity="0.95" />
      <text x={hoverX + 10} y={hoverY - 1} fill="#fafafa"
        font-size="8" font-family="JetBrains Mono, monospace">{formatY(data[hoverIndex].value)}</text>
    {/if}
  </svg>

  {#if startLabel || endLabel}
    <div class="flex justify-between text-[9px] text-zinc-500 mt-1" style="padding-left: {MARGIN_LEFT / WIDTH * 100}%; padding-right: {MARGIN_RIGHT / WIDTH * 100}%">
      <span>{startLabel}</span>
      <span>{endLabel}</span>
    </div>
  {/if}
</div>