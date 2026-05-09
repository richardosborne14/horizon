<script lang="ts">
  /**
   * InsightCards — renders the top 5 ranked actionable insights from the insights engine.
   * Color-coded by severity: critical (rose), warning (amber), opportunity (teal), positive (emerald).
   */
  import { fmt, fmtK } from '$lib/utils/format';

  export let insights: Array<{
    id: string;
    category: string;
    severity: string;
    title: string;
    description: string;
    impact_wealth: string;
    action: string;
    priority: number;
  }> = [];

  const severityStyles: Record<string, { bg: string; border: string; text: string; dot: string }> = {
    critical: { bg: 'bg-rose-950/15', border: 'border-rose-900/30', text: 'text-rose-300', dot: 'bg-rose-500' },
    warning: { bg: 'bg-amber-950/15', border: 'border-amber-900/30', text: 'text-amber-300', dot: 'bg-amber-500' },
    opportunity: { bg: 'bg-teal-950/10', border: 'border-teal-900/20', text: 'text-teal-300', dot: 'bg-teal-500' },
    positive: { bg: 'bg-emerald-950/10', border: 'border-emerald-900/20', text: 'text-emerald-300', dot: 'bg-emerald-500' },
  };

  function fmtImpact(value: string): string {
    const n = parseFloat(value);
    if (isNaN(n) || n === 0) return '';
    const abs = Math.abs(n);
    if (n > 0) return `+${fmtK(String(abs))}`;
    return `-${fmtK(String(abs))}`;
  }
</script>

{#if insights.length > 0}
  <div class="space-y-3">
    <p class="text-xs font-semibold text-zinc-300">💡 Recommandations</p>
    {#each insights as ins (ins.id)}
      {@const s = severityStyles[ins.severity] || severityStyles.positive}
      <div class="{s.bg} border {s.border} rounded-xl p-3">
        <div class="flex items-start gap-2 mb-1">
          <span class="w-2 h-2 {s.dot} rounded-full mt-1.5 flex-shrink-0"></span>
          <p class="text-xs font-semibold {s.text}">{ins.title}</p>
        </div>
        <p class="text-[10px] text-zinc-400 leading-relaxed">{ins.description}</p>
        <div class="flex items-center justify-between mt-2">
          <span class="text-[10px] text-zinc-500">{ins.action}</span>
          {#if ins.impact_wealth !== '0' && ins.impact_wealth !== '0.00'}
            <span class="text-[10px] font-mono {parseFloat(ins.impact_wealth) > 0 ? 'text-emerald-400' : 'text-rose-400'}">
              {fmtImpact(ins.impact_wealth)}
            </span>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{/if}