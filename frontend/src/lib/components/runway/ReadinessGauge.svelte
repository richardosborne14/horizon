<script lang="ts">
  /**
   * ReadinessGauge — circular SVG gauge displaying the retirement readiness score (0–100).
   *
   * Animated arc fill on mount. Color-coded bands:
   *   rose (0–20) → amber (21–40) → yellow (41–60) → teal (61–80) → emerald (81–100).
   *
   * Props:
   *   score: 0–100
   *   label: Band label ("Fragile", etc.)
   *   color: Band color key
   *   summary: One-sentence explanation
   *   components: Dict of component sub-scores
   */
  import { onMount } from 'svelte';
  import { tweened } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';

  export let score: number = 0;
  export let label: string = '—';
  export let color: string = 'rose';
  export let summary: string = '';
  export let components: Record<string, number> = {};

  // ── Animation ──────────────────────────────────────────────────────────
  const animatedScore = tweened(0, {
    duration: 1500,
    easing: cubicOut,
  });

  let visible = false;
  onMount(() => {
    visible = true;
    animatedScore.set(score);
  });

  $: animatedScore.set(score);

  // ── SVG constants ──────────────────────────────────────────────────────
  const SIZE = 140;
  const STROKE = 10;
  const RADIUS = (SIZE - STROKE) / 2;
  const CIRCUM = 2 * Math.PI * RADIUS;
  const CENTER = SIZE / 2;

  $: dashOffset = CIRCUM * (1 - $animatedScore / 100);

  // ── Color mapping ──────────────────────────────────────────────────────
  const bandColors: Record<string, { stroke: string; trail: string }> = {
    rose: { stroke: '#f43f5e', trail: '#f43f5e20' },
    amber: { stroke: '#f59e0b', trail: '#f59e0b20' },
    yellow: { stroke: '#eab308', trail: '#eab30820' },
    teal: { stroke: '#2dd4bf', trail: '#2dd4bf20' },
    emerald: { stroke: '#10b981', trail: '#10b98120' },
  };

  $: c = bandColors[color] || bandColors.teal;

  // ── Component display labels ───────────────────────────────────────────
  const compLabels: Record<string, string> = {
    goal_coverage: 'Couverture objectif',
    wealth_durability: 'Durée patrimoine',
    savings_rate: "Taux d'épargne",
    diversification: 'Diversification',
    growth_trajectory: 'Croissance',
    buffer_adequacy: 'Fonds urgence',
  };

  let expanded = false;
  function toggle() {
    expanded = !expanded;
  }
</script>

<div class="flex flex-col items-center gap-2">
  <!-- ── Circular gauge ────────────────────────────────────────────────── -->
  <div class="relative" style="width:{SIZE}px;height:{SIZE}px">
    <svg viewBox="0 0 {SIZE} {SIZE}" class="transform -rotate-90" width={SIZE} height={SIZE}>
      <!-- Trail circle -->
      <circle
        cx={CENTER} cy={CENTER} r={RADIUS}
        fill="none" stroke={c.trail} stroke-width={STROKE}
        stroke-linecap="round"
      />
      <!-- Animated progress arc -->
      {#if visible}
        <circle
          cx={CENTER} cy={CENTER} r={RADIUS}
          fill="none" stroke={c.stroke} stroke-width={STROKE}
          stroke-linecap="round"
          stroke-dasharray={CIRCUM}
          stroke-dashoffset={dashOffset}
          style="transition: stroke-dashoffset 0.8s ease-out"
        />
      {/if}
    </svg>
    <!-- Center text -->
    <div class="absolute inset-0 flex flex-col items-center justify-center">
      <span class="text-2xl font-bold font-mono text-white">{$animatedScore}</span>
      <span class="text-[8px] text-zinc-500">/ 100</span>
    </div>
  </div>

  <!-- ── Label ─────────────────────────────────────────────────────────── -->
  <p class="text-sm font-semibold" style="color: {c.stroke}">{label}</p>

  <!-- ── Summary ───────────────────────────────────────────────────────── -->
  {#if summary}
    <p class="text-[10px] text-zinc-400 text-center max-w-[280px] leading-relaxed">{summary}</p>
  {/if}

  <!-- ── Component breakdown (expandable) ──────────────────────────────── -->
  {#if Object.keys(components).length > 0}
    <button
      on:click={toggle}
      class="text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors mt-1 underline underline-offset-2"
    >
      {expanded ? 'Masquer le détail' : 'Voir le détail'}
    </button>

    {#if expanded}
      <div class="w-full space-y-1.5 mt-1">
        {#each Object.entries(components) as [key, val]}
          <div class="flex items-center gap-2">
            <span class="text-[9px] text-zinc-500 w-28 text-right flex-shrink-0">{compLabels[key] || key}</span>
            <div class="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div class="h-full rounded-full transition-all duration-500" style="width:{val}%; background:{c.stroke}"></div>
            </div>
            <span class="text-[9px] font-mono text-zinc-400 w-8 text-right">{val}</span>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>