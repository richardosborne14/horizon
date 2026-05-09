<script lang="ts">
  /**
   * CostEventList — renders an editable list of cost events with visual state indicators.
   *
   * Each event shows:
   * - Dot indicator: purple (active), grey (future), faded (past)
   * - Editable label
   * - Age range readout
   * - Amount input (right-aligned)
   * - Frequency badge
   * - Remove button (user events)
   *
   * Events are sorted: active first, then future, then past.
   */
  import { createEventDispatcher } from 'svelte';
  import { _ } from 'svelte-i18n';

  export let events: Array<{
    id: string;
    label: string;
    from_age: number;
    to_age: number;
    amount: string;
    frequency: string;
    source: string;
    is_active: boolean;
  }> = [];

  export let entityAge: number = 0;
  export let readonly: boolean = false;

  const dispatch = createEventDispatcher();

  // ── State helpers ──────────────────────────────────────────────────────────

  function getEventState(event: typeof events[0]): 'active' | 'future' | 'past' {
    if (entityAge > event.to_age) return 'past';
    if (entityAge >= event.from_age) return 'active';
    return 'future';
  }

  function stateDotClass(event: typeof events[0]): string {
    const state = getEventState(event);
    if (state === 'active') return 'bg-purple-400';
    if (state === 'future') return 'bg-zinc-500';
    return 'bg-zinc-700';
  }

  function stateRowClass(event: typeof events[0]): string {
    const state = getEventState(event);
    if (state === 'active') return 'bg-purple-500/5 border-purple-500/10';
    if (state === 'past') return 'opacity-40';
    return '';
  }

  function freqLabel(frequency: string): string {
    if (frequency === 'monthly') return '€/mois';
    if (frequency === 'annual') return '€/an';
    return 'une fois';
  }

  // ── Sorting ────────────────────────────────────────────────────────────────

  $: sortedEvents = [...events].sort((a, b) => {
    const order = { active: 0, future: 1, past: 2 };
    const aState = getEventState(a);
    const bState = getEventState(b);
    return (order[aState] || 0) - (order[bState] || 0);
  });

  // ── Event handlers ─────────────────────────────────────────────────────────

  function onLabelChange(idx: number, value: string) {
    events[idx].label = value;
    dispatch('change', { events: [...events] });
  }

  function onAmountChange(idx: number, value: string) {
    events[idx].amount = value;
    dispatch('change', { events: [...events] });
  }

  function onRemove(idx: number) {
    const updated = events.filter((_, i) => i !== idx);
    dispatch('change', { events: updated });
  }

</script>

<div class="space-y-0.5" data-coco-desc="Liste des dépenses liées à cet élément de vie">
  {#each sortedEvents as event, i}
    <div
      class="flex items-center gap-2 text-xs p-2 rounded {stateRowClass(event)}"
      data-coco-desc={`Dépense ${event.label} : ${event.amount}€/${event.frequency === 'monthly' ? 'mois' : event.frequency === 'annual' ? 'an' : 'une fois'} de ${event.from_age} à ${event.to_age} ans`}
    >
      <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {stateDotClass(event)}" />

      <input
        type="text"
        value={event.label}
        class="flex-1 bg-transparent text-zinc-300 text-xs focus:outline-none focus:text-zinc-100 min-w-0"
        on:blur={(e) => onLabelChange(i, (e.target as HTMLInputElement).value)}
        disabled={readonly}
      />

      <span class="text-zinc-500 text-[10px] font-mono flex-shrink-0">
        {event.from_age}→{event.to_age} ans
      </span>

      <input
        type="number"
        step="0.01"
        min="0"
        value={parseFloat(event.amount) || 0}
        class="w-16 bg-zinc-800/40 border border-zinc-700/30 rounded px-1.5 py-0.5 text-xs font-mono text-right flex-shrink-0 focus:border-purple-500/50 focus:outline-none"
        on:blur={(e) => onAmountChange(i, (e.target as HTMLInputElement).value)}
        disabled={readonly}
      />

      <span class="text-[10px] text-zinc-500 flex-shrink-0">{freqLabel(event.frequency)}</span>

      {#if !readonly}
        <button
          class="text-zinc-600 hover:text-rose-400 flex-shrink-0 text-xs"
          on:click={() => onRemove(i)}
          data-coco-desc={`Supprimer la dépense ${event.label}`}
        >✕</button>
      {/if}
    </div>
  {/each}

  {#if !readonly}
    <button
      class="w-full text-center text-[10px] text-zinc-500 hover:text-zinc-300 py-1.5 border border-dashed border-zinc-700/50 rounded hover:border-zinc-600/50 transition-colors"
      on:click={() => {
        dispatch('addCustom');
      }}
      data-coco-desc="Ajouter une dépense personnalisée pour cet élément"
    >
      + {$_('life.kids.add_custom_expense', 'Ajouter une dépense')}
    </button>
  {/if}
</div>