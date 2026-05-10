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

  /** Find the index of event with given id in the original `events` array. */
  function originalIndex(eventId: string): number {
    return events.findIndex(e => e.id === eventId);
  }

  function onLabelChange(eventId: string, value: string) {
    const idx = originalIndex(eventId);
    if (idx === -1) return;
    events[idx].label = value;
    dispatch('change', { events: [...events] });
  }

  function onAmountChange(eventId: string, value: string) {
    const idx = originalIndex(eventId);
    if (idx === -1) return;
    events[idx].amount = value;
    dispatch('change', { events: [...events] });
  }

  function onAgeChange(eventId: string, field: 'from_age' | 'to_age', value: number) {
    const idx = originalIndex(eventId);
    if (idx === -1) return;
    events[idx][field] = value;
    dispatch('change', { events: [...events] });
  }

  function onFrequencyChange(eventId: string, value: string) {
    const idx = originalIndex(eventId);
    if (idx === -1) return;
    events[idx].frequency = value;
    dispatch('change', { events: [...events] });
  }

  function onRemove(eventId: string) {
    const updated = events.filter(e => e.id !== eventId);
    dispatch('change', { events: updated });
  }

  function handleAdd() {
    dispatch('addCustom');
  }

</script>

<div class="space-y-0.5" data-coco-desc="Liste des dépenses liées à cet élément de vie">
  {#each sortedEvents as event}
    <div
      class="flex items-center gap-2 text-xs p-2 rounded {stateRowClass(event)}"
      data-coco-desc={`Dépense ${event.label} : ${event.amount}€/${event.frequency === 'monthly' ? 'mois' : event.frequency === 'annual' ? 'an' : 'une fois'} de ${event.from_age} à ${event.to_age} ans`}
    >
      <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {stateDotClass(event)}"></span>

      <input
        type="text"
        value={event.label}
        class="flex-1 bg-transparent text-zinc-300 text-xs focus:outline-none focus:text-zinc-100 min-w-0"
        on:blur={(e) => onLabelChange(event.id, (e.target as HTMLInputElement).value)}
        disabled={readonly}
      />

      <!-- Age range inputs -->
      <input
        type="number"
        min="0"
        max="99"
        value={event.from_age}
        class="w-10 bg-zinc-800/40 border border-zinc-700/30 rounded px-1 py-0.5 text-xs text-center font-mono flex-shrink-0 focus:border-purple-500/50 focus:outline-none"
        on:blur={(e) => onAgeChange(event.id, 'from_age', parseInt((e.target as HTMLInputElement).value) || 0)}
        disabled={readonly}
        data-coco-desc={`Âge de début pour ${event.label}`}
      />
      <span class="text-zinc-600 text-[10px] flex-shrink-0">→</span>
      <input
        type="number"
        min="0"
        max="99"
        value={event.to_age}
        class="w-10 bg-zinc-800/40 border border-zinc-700/30 rounded px-1 py-0.5 text-xs text-center font-mono flex-shrink-0 focus:border-purple-500/50 focus:outline-none"
        on:blur={(e) => onAgeChange(event.id, 'to_age', parseInt((e.target as HTMLInputElement).value) || 0)}
        disabled={readonly}
        data-coco-desc={`Âge de fin pour ${event.label}`}
      />
      <span class="text-zinc-500 text-[10px] flex-shrink-0">ans</span>

      <input
        type="number"
        step="0.01"
        min="0"
        value={parseFloat(event.amount) || 0}
        class="w-16 bg-zinc-800/40 border border-zinc-700/30 rounded px-1.5 py-0.5 text-xs font-mono text-right flex-shrink-0 focus:border-purple-500/50 focus:outline-none"
        on:blur={(e) => onAmountChange(event.id, (e.target as HTMLInputElement).value)}
        disabled={readonly}
      />

      <!-- Editable frequency selector -->
      <select
        value={event.frequency}
        class="w-20 bg-zinc-800/40 border border-zinc-700/30 rounded px-1 py-0.5 text-[10px] text-zinc-300 flex-shrink-0 focus:border-purple-500/50 focus:outline-none"
        on:change={(e) => onFrequencyChange(event.id, (e.target as HTMLSelectElement).value)}
        disabled={readonly}
        data-coco-desc={`Fréquence de la dépense ${event.label}`}
      >
        <option value="monthly">€/mois</option>
        <option value="annual">€/an</option>
        <option value="once">une fois</option>
      </select>

      {#if !readonly}
        <button
          class="text-zinc-600 hover:text-rose-400 flex-shrink-0 text-xs"
          on:click={() => onRemove(event.id)}
          data-coco-desc={`Supprimer la dépense ${event.label}`}
        >✕</button>
      {/if}
    </div>
  {/each}

  {#if !readonly}
    <button
      class="w-full text-center text-[10px] text-zinc-500 hover:text-zinc-300 py-1.5 border border-dashed border-zinc-700/50 rounded hover:border-zinc-600/50 transition-colors"
      on:click={handleAdd}
      data-coco-desc="Ajouter une dépense personnalisée pour cet élément"
    >
      + {$_('life.kids.add_custom_expense', 'Ajouter une dépense')}
    </button>
  {/if}
</div>
