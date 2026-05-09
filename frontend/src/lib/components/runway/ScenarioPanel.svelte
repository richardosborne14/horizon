<script lang="ts">
  /**
   * ScenarioPanel — "Et si...?" scenario comparison panel (TASK-5.7).
   *
   * Sliding panel that lets the user fork their current plan, tweak key
   * parameters, and see both projections side-by-side. Does NOT modify
   * saved data — pure frontend exploration.
   */
  import { createEventDispatcher } from 'svelte';
  import { fmt, fmtK } from '$lib/utils/format';

  export let open = false;
  export let loading = false;
  export let currentScale = 'moderate';
  export let baseSummary: any = null;
  export let scenarioResult: any = null;

  const dispatch = createEventDispatcher();

  // ── Preset scenarios ──────────────────────────────────────────────
  const PRESETS = [
    {
      id: 'effort_max',
      label: '💪 Effort maximum',
      desc: 'Épargne +50%, dépenses -10%, croissance ambitieuse',
      overrides: { monthly_savings_bonus: 0.5, expenses_delta: -0.10, growth_rate: 0.06 },
    },
    {
      id: 'retraite_anticipee',
      label: '🏖️ Retraite anticipée',
      desc: 'Retraite à 62 ans, même épargne',
      overrides: { retirement_age: 62 },
    },
    {
      id: 'sans_projet',
      label: '🏠 Sans le projet immobilier',
      desc: 'Simulation sans les projets d\'investissement',
      overrides: { disable_projects: true },
    },
  ];

  // ── Slider state ──────────────────────────────────────────────────
  let monthlySavings = 750;
  let retirementAge = 67;
  let growthRate = 0.01;
  let expensesDelta = 0;

  let initialSavings = 750;
  let initialRetirementAge = 67;
  let initialGrowthRate = 0.01;

  let activePreset: string | null = null;

  $: savingsPercent = initialSavings > 0 ? Math.round((monthlySavings / initialSavings - 1) * 100) : 0;
  $: ageDelta = retirementAge - initialRetirementAge;
  $: hasChanges = monthlySavings !== initialSavings || retirementAge !== initialRetirementAge
    || growthRate !== initialGrowthRate || expensesDelta !== 0;

  let debounceTimer: ReturnType<typeof setTimeout>;

  function applyPreset(presetId: string) {
    activePreset = presetId;
    const preset = PRESETS.find((p) => p.id === presetId);
    if (!preset) return;

    if (preset.overrides.retirement_age) {
      retirementAge = preset.overrides.retirement_age;
    }
    if (preset.overrides.monthly_savings_bonus) {
      monthlySavings = Math.round(initialSavings * (1 + preset.overrides.monthly_savings_bonus) / 50) * 50;
    }
    if (preset.overrides.growth_rate) {
      growthRate = preset.overrides.growth_rate;
    }
    if (preset.overrides.expenses_delta) {
      expensesDelta = -500; // expenses delta is absolute
    }
    if (preset.overrides.disable_projects) {
      // handled downstream
    }
    requestCompare();
  }

  function requestCompare() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const overrides: any = {};
      if (monthlySavings !== initialSavings) {
        overrides.monthly_savings = monthlySavings;
      }
      if (retirementAge !== initialRetirementAge) {
        overrides.target_retirement_age = retirementAge;
      }
      if (growthRate !== initialGrowthRate) {
        overrides.growth_rate = growthRate;
      }
      if (expensesDelta !== 0) {
        overrides.monthly_expenses_delta = expensesDelta;
      }
      if (activePreset === 'sans_projet') {
        // Need to send a flag — handled via overrides in comparison
      }
      dispatch('compare', { overrides, preset: activePreset });
    }, 500);
  }

  function resetAll() {
    monthlySavings = initialSavings;
    retirementAge = initialRetirementAge;
    growthRate = initialGrowthRate;
    expensesDelta = 0;
    activePreset = null;
    dispatch('reset');
  }

  // Initialize from base summary when it arrives
  $: if (baseSummary && initialSavings === 750) {
    // Try to extract savings from profile
    const passiveYearly = parseFloat(baseSummary.final_passive_monthly || '0') * 12;
    // Rough extraction — override when profile data available
  }

  export function initFromProfile(profile: any, savingsTotal: number) {
    initialSavings = savingsTotal || 750;
    monthlySavings = initialSavings;
    initialRetirementAge = profile?.target_retirement_age || 67;
    retirementAge = initialRetirementAge;
    initialGrowthRate = profile?.growth_preset === 'ambitieux' ? 0.06
      : profile?.growth_preset === 'prudent' ? 0.0
      : profile?.growth_rate_custom || 0.01;
    growthRate = initialGrowthRate;
  }

  function onChangeSavings(e: Event) {
    monthlySavings = parseInt((e.target as HTMLInputElement).value);
    activePreset = null;
    requestCompare();
  }

  function onChangeAge(e: Event) {
    retirementAge = parseInt((e.target as HTMLInputElement).value);
    activePreset = null;
    requestCompare();
  }

  function onSelectGrowth(rate: number) {
    growthRate = rate;
    activePreset = null;
    requestCompare();
  }

  function onChangeExpenses(e: Event) {
    expensesDelta = parseInt((e.target as HTMLInputElement).value);
    activePreset = null;
    requestCompare();
  }

  function applyScenario() {
    dispatch('apply');
  }

  function close() {
    dispatch('close');
  }
</script>

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="fixed inset-0 z-50 flex justify-end" on:click|self={close}>
    <!-- Backdrop -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" on:click={close}></div>

    <!-- Panel -->
    <div class="relative w-full max-w-md bg-zinc-950 border-l border-zinc-800 h-full overflow-y-auto shadow-2xl">
      <!-- Header -->
      <div class="sticky top-0 bg-zinc-950/95 backdrop-blur border-b border-zinc-800 px-5 py-4 flex items-center justify-between z-10">
        <h2 class="text-sm font-semibold text-white">Et si...?</h2>
        <button on:click={close} class="text-zinc-500 hover:text-zinc-300 p-1">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M4 4l8 8M12 4l-8 8"/>
          </svg>
        </button>
      </div>

      <div class="p-5 space-y-5">
        <!-- Preset scenarios -->
        <div>
          <p class="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Scénarios prédéfinis</p>
          <div class="grid grid-cols-1 gap-2">
            {#each PRESETS as preset}
              <button
                class="text-left px-3 py-2.5 rounded-lg border text-xs transition-all
                  {activePreset === preset.id
                    ? 'border-teal-500/50 bg-teal-950/20 text-teal-200'
                    : 'border-zinc-800/60 bg-zinc-900/30 text-zinc-400 hover:border-zinc-700 hover:text-zinc-300'}"
                on:click={() => applyPreset(preset.id)}
              >
                <span class="font-medium text-white">{preset.label}</span>
                <span class="block text-[10px] text-zinc-500 mt-0.5">{preset.desc}</span>
              </button>
            {/each}
          </div>
        </div>

        <!-- Divider -->
        <div class="border-t border-zinc-800/50"></div>

        <!-- Manual controls -->
        <p class="text-[10px] text-zinc-500 uppercase tracking-wider">Ajustements manuels</p>

        <!-- Savings slider -->
        <div>
          <div class="flex justify-between items-baseline mb-1.5">
            <label class="text-[11px] text-zinc-400">Épargne mensuelle</label>
            <span class="text-xs font-mono text-white">{monthlySavings}€/mois
              {#if savingsPercent !== 0}
                <span class="ml-1 {savingsPercent > 0 ? 'text-teal-400' : 'text-rose-400'}">
                  {savingsPercent > 0 ? '+' : ''}{savingsPercent}%
                </span>
              {/if}
            </span>
          </div>
          <input type="range" min="0" max="5000" step="50" value={monthlySavings}
            on:input={onChangeSavings}
            class="w-full h-1.5 appearance-none bg-zinc-800 rounded-full accent-teal-500" />
          <div class="flex justify-between text-[9px] text-zinc-600 mt-0.5">
            <span>0€</span><span>5 000€</span>
          </div>
        </div>

        <!-- Retirement age slider -->
        <div>
          <div class="flex justify-between items-baseline mb-1.5">
            <label class="text-[11px] text-zinc-400">Âge de retraite</label>
            <span class="text-xs font-mono text-white">{retirementAge} ans
              {#if ageDelta !== 0}
                <span class="ml-1 {ageDelta > 0 ? 'text-amber-400' : 'text-teal-400'}">
                  {ageDelta > 0 ? '+' : ''}{ageDelta} ans
                </span>
              {/if}
            </span>
          </div>
          <input type="range" min="55" max="80" step="1" value={retirementAge}
            on:input={onChangeAge}
            class="w-full h-1.5 appearance-none bg-zinc-800 rounded-full accent-teal-500" />
          <div class="flex justify-between text-[9px] text-zinc-600 mt-0.5">
            <span>55 ans</span><span>80 ans</span>
          </div>
        </div>

        <!-- Growth rate selector -->
        <div>
          <label class="text-[11px] text-zinc-400 block mb-1.5">Croissance du CA</label>
          <div class="flex gap-1.5">
            {#each [{ rate: 0, label: '0%' }, { rate: 0.01, label: '1%' }, { rate: 0.03, label: '3%' }, { rate: 0.06, label: '6%' }] as opt}
              <button
                class="flex-1 py-1.5 rounded-lg text-xs font-mono border transition-all
                  {growthRate === opt.rate
                    ? 'border-teal-500/50 bg-teal-950/20 text-teal-200'
                    : 'border-zinc-800/60 bg-zinc-900/30 text-zinc-500 hover:text-zinc-300'}"
                on:click={() => onSelectGrowth(opt.rate)}
              >{opt.label}</button>
            {/each}
          </div>
        </div>

        <!-- Expenses delta -->
        <div>
          <div class="flex justify-between items-baseline mb-1.5">
            <label class="text-[11px] text-zinc-400">Dépenses mensuelles</label>
            <span class="text-xs font-mono text-white">
              {#if expensesDelta < 0}-{-expensesDelta}€{:else if expensesDelta > 0}+{expensesDelta}€{:else}inchangé{/if}
            </span>
          </div>
          <input type="range" min="-1000" max="1000" step="100" value={expensesDelta}
            on:input={onChangeExpenses}
            class="w-full h-1.5 appearance-none bg-zinc-800 rounded-full accent-teal-500" />
          <div class="flex justify-between text-[9px] text-zinc-600 mt-0.5">
            <span>-1 000€</span><span>+1 000€</span>
          </div>
        </div>

        <!-- Divider -->
        <div class="border-t border-zinc-800/50"></div>

        <!-- Loading state -->
        {#if loading}
          <div class="text-center py-4">
            <div class="animate-spin w-5 h-5 border-2 border-teal-500/30 border-t-teal-500 rounded-full mx-auto"></div>
            <p class="text-[10px] text-zinc-500 mt-2">Calcul en cours...</p>
          </div>
        {/if}

        <!-- Delta summary -->
        {#if scenarioResult?.delta}
          <div class="space-y-2">
            <p class="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Impact du scénario</p>
            <div class="grid grid-cols-2 gap-2">
              <div class="bg-zinc-800/30 border border-zinc-800/40 rounded-lg p-2.5">
                <p class="text-[9px] text-zinc-500">Patrimoine final</p>
                <p class="text-sm font-mono font-bold {parseFloat(scenarioResult.delta.final_wealth) >= 0 ? 'text-teal-400' : 'text-rose-400'}">{scenarioResult.delta.final_wealth}</p>
              </div>
              <div class="bg-zinc-800/30 border border-zinc-800/40 rounded-lg p-2.5">
                <p class="text-[9px] text-zinc-500">Revenu passif</p>
                <p class="text-sm font-mono font-bold {parseFloat(scenarioResult.delta.passive_monthly) >= 0 ? 'text-emerald-400' : 'text-rose-400'}">{scenarioResult.delta.passive_monthly}</p>
              </div>
            </div>
            {#if scenarioResult.delta.goal_reached_year_delta}
              <div class="bg-zinc-800/30 border border-zinc-800/40 rounded-lg p-2.5">
                <p class="text-[9px] text-zinc-500">Objectif de revenu</p>
                <p class="text-xs font-mono text-zinc-300">{scenarioResult.delta.goal_reached_year_delta}</p>
              </div>
            {/if}
            {#if scenarioResult.delta.wealth_exhaustion_delta}
              <div class="bg-zinc-800/30 border border-zinc-800/40 rounded-lg p-2.5">
                <p class="text-[9px] text-zinc-500">Épuisement du patrimoine</p>
                <p class="text-xs font-mono text-zinc-300">{scenarioResult.delta.wealth_exhaustion_delta}</p>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Action buttons -->
        <div class="flex gap-2 pt-2">
          <button
            class="flex-1 py-2 rounded-lg bg-teal-600/80 hover:bg-teal-600 text-xs font-medium text-white transition-colors disabled:opacity-30"
            disabled={!hasChanges || loading}
            on:click={applyScenario}
          >
            Appliquer ce scénario
          </button>
          <button
            class="px-3 py-2 rounded-lg border border-zinc-800 bg-zinc-900/30 text-xs text-zinc-400 hover:text-zinc-300 transition-colors"
            disabled={!hasChanges}
            on:click={resetAll}
          >
            Réinitialiser
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}