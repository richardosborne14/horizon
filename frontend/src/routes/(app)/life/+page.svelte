<script lang="ts">
  /**
   * Life page — manage life entities (kids, pets, cars, tech) and recurring expenses.
   *
   * Sections:
   * 1. Sky info box — intro text
   * 2. Kids (purple accent) — expandable cards with full lifecycle events
   * 3. Pets (emerald accent) — type-specific cost events
   * 4. Cars (amber accent) — fuel-type costs, CT inspections, replacement
   * 5. Tech (sky accent) — replacement cycles, accessories
   * 6. Recurring (rose accent) — time-bounded annual expenses
   */
  import { _ } from 'svelte-i18n';
  import type { PageData } from './$types';
  import CostEventList from '$lib/components/life/CostEventList.svelte';

  export let data: PageData;

  // ── State ──────────────────────────────────────────────────────────────────

  let kids = data.kids ?? [];
  let pets = data.pets ?? [];
  let cars = data.cars ?? [];
  let tech = data.tech ?? [];
  let recurringExpenses = data.recurring ?? [];

  let showKidForm = false;
  let showPetForm = false;
  let showCarForm = false;
  let showTechForm = false;

  // Form fields
  let newKidName = '';
  let newKidBirth = '';
  let newPetName = '';
  let newPetType = 'dog';
  let newPetBirth = '';
  let newCarName = '';
  let newCarFuel = 'petrol';
  let newCarDate = '';
  let newCarCycle = 8;
  let newCarReplaceCost = 18000;
  let newTechName = '';
  let newTechType = 'laptop';
  let newTechDate = '';
  let newTechCycle = 3;
  let newTechReplaceCost = 1200;

  let deleteConfirm: { type: string; id: string; name: string } | null = null;

  // ── API helpers ────────────────────────────────────────────────────────────

  // WHY /api prefix, not PUBLIC_API_URL:
  //   The Vite dev proxy (vite.config.ts) forwards /api/* to the backend.
  //   Using PUBLIC_API_URL (http://localhost:48002) bypasses the proxy and
  //   hits CORS — the backend doesn't have CORS configured for :48178 origins.
  //   Relative paths go to same origin (:48178) → Vite proxy → backend.
  const API_BASE = '/api';

  async function apiFetch(path: string, options: RequestInit = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      credentials: 'include',
    });
    if (!res.ok && res.status !== 204) {
      const err = await res.text();
      console.error(`API error ${res.status}: ${err}`);
      return null;
    }
    if (res.status === 204) return null;
    return res.json();
  }

  // ── Entity CRUD ────────────────────────────────────────────────────────────

  async function addEntity(type: string, payload: Record<string, any>) {
    const entity = await apiFetch('/life-entities', {
      method: 'POST',
      body: JSON.stringify({
        entity_type: type,
        ...payload,
        cost_events: [],
      }),
    });
    if (entity) {
      if (type === 'kid') kids = [...kids, entity];
      else if (type === 'pet') pets = [...pets, entity];
      else if (type === 'car') cars = [...cars, entity];
      else if (type === 'tech') tech = [...tech, entity];
    }
  }

  async function updateEntity(id: string, payload: Record<string, any>) {
    const entity = await apiFetch(`/life-entities/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    if (entity) {
      const updater = (list: any[]) => list.map(e => e.id === id ? entity : e);
      kids = updater(kids);
      pets = updater(pets);
      cars = updater(cars);
      tech = updater(tech);
    }
  }

  async function deleteEntity(id: string) {
    await apiFetch(`/life-entities/${id}`, { method: 'DELETE' });
    kids = kids.filter(e => e.id !== id);
    pets = pets.filter(e => e.id !== id);
    cars = cars.filter(e => e.id !== id);
    tech = tech.filter(e => e.id !== id);
    deleteConfirm = null;
  }

  async function updateCostEvents(entityId: string, costEvents: any[]) {
    await updateEntity(entityId, { cost_events: costEvents });
  }

  async function addCustomEvent(entityId: string, events: any[]) {
    const newEvent = {
      id: 'evt-' + Math.random().toString(36).slice(2, 10),
      label: 'Nouvelle dépense',
      from_age: 0,
      to_age: 18,
      amount: '0.00',
      frequency: 'monthly',
      source: 'user',
      is_active: true,
    };
    await updateCostEvents(entityId, [...events, newEvent]);
  }

  // ── Recurring expense CRUD ─────────────────────────────────────────────────

  async function addRecurring() {
    const exp = await apiFetch('/recurring-expenses', {
      method: 'POST',
      body: JSON.stringify({
        label: '',
        annual_amount: 0,
        from_year: 2026,
        to_year: 2031,
      }),
    });
    if (exp) recurringExpenses = [...recurringExpenses, exp];
  }

  async function updateRecurring(id: string, payload: Record<string, any>) {
    const exp = await apiFetch(`/recurring-expenses/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    if (exp) {
      recurringExpenses = recurringExpenses.map(e => e.id === id ? exp : e);
    }
  }

  async function deleteRecurring(id: string) {
    await apiFetch(`/recurring-expenses/${id}`, { method: 'DELETE' });
    recurringExpenses = recurringExpenses.filter(e => e.id !== id);
  }

  // ── Add handlers ───────────────────────────────────────────────────────────

  async function handleAddKid() {
    if (!newKidName || !newKidBirth) return;
    await addEntity('kid', { name: newKidName, reference_date: newKidBirth, metadata: {} });
    newKidName = '';
    newKidBirth = '';
    showKidForm;
    showKidForm = false;
  }

  async function handleAddPet() {
    if (!newPetName || !newPetBirth) return;
    await addEntity('pet', {
      name: newPetName,
      reference_date: newPetBirth,
      metadata: { pet_type: newPetType },
    });
    newPetName = '';
    newPetBirth = '';
    showPetForm = false;
  }

  async function handleAddCar() {
    if (!newCarName || !newCarDate) return;
    await addEntity('car', {
      name: newCarName,
      reference_date: newCarDate,
      metadata: {
        fuel_type: newCarFuel,
        replace_cycle: newCarCycle,
        replace_cost: newCarReplaceCost,
      },
    });
    newCarName = '';
    newCarDate = '';
    showCarForm = false;
  }

  async function handleAddTech() {
    if (!newTechName || !newTechDate) return;
    await addEntity('tech', {
      name: newTechName,
      reference_date: newTechDate,
      metadata: {
        device_type: newTechType,
        replace_cycle: newTechCycle,
        replace_cost: newTechReplaceCost,
      },
    });
    newTechName = '';
    newTechDate = '';
    showTechForm = false;
  }

  // ── Debounced save for recurring ───────────────────────────────────────────

  let debounceTimers: Record<string, ReturnType<typeof setTimeout>> = {};

  function debouncedSaveRecurring(id: string, field: string, value: any) {
    if (debounceTimers[id]) clearTimeout(debounceTimers[id]);
    debounceTimers[id] = setTimeout(() => {
      updateRecurring(id, { [field]: value });
    }, 800);
  }

  // ── i18n keys ──────────────────────────────────────────────────────────────
  // WHY inline $_() in template, not $: reactive statements:
  //   Svelte 5 runes mode rewrites $variableName inside function calls as
  //   store_get — which fails when the variable is a plain string, not a store.
  //   See AuthLayout.svelte for full explanation. All translations called
  //   directly in the template with $_('key', 'default').
</script>

<svelte:head>
  <title>{$_('life.title', 'Vie')} — Horizon</title>
</svelte:head>

<div class="space-y-5 max-w-3xl mx-auto pb-20">
  <!-- ── Info box ─────────────────────────────────────────────────────────── -->
  <div
    class="bg-sky-950/20 border border-sky-900/30 rounded-xl p-4"
    data-coco-desc="Introduction à la page Vie. Chaque élément de vie (enfant, animal, voiture, appareil) a des coûts qui évoluent avec le temps."
  >
    <p class="text-xs text-sky-300/80">
      <strong class="text-sky-200">{$_('life.title', 'Vie')}.</strong> {$_('life.intro', 'Entités de vie. Enfants, animaux, voitures, tech — chaque élément a un cycle de coûts qui évolue avec le temps.')}
    </p>
  </div>

  <!-- ── Kids ─────────────────────────────────────────────────────────────── -->
  <div
    class="bg-zinc-900/50 border border-purple-800/30 rounded-xl p-4"
    data-coco-desc="Section enfants. Chaque enfant a un cycle de coûts éducatifs complet de la crèche aux études supérieures."
  >
    <h3 class="text-sm font-semibold text-purple-300 mb-1">{$_('life.kids.title', 'Enfants')} 👶</h3>

    {#each kids as kid (kid.id)}
      <div class="bg-zinc-900/70 border border-zinc-800/50 rounded-lg p-3 mb-3" data-coco-desc={`Fiche enfant : ${kid.name}, ${kid.current_age} ans`}>
        <div class="flex items-center gap-2 mb-2">
          <input
            type="text"
            value={kid.name}
            class="flex-1 bg-transparent text-zinc-200 text-sm font-medium focus:outline-none"
            on:blur={(e) => updateEntity(kid.id, { name: (e.target as HTMLInputElement).value })}
          />
          <span class="text-zinc-400 text-xs">{kid.current_age} ans</span>
          <input
            type="date"
            value={kid.reference_date}
            class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-0.5 text-xs text-zinc-300"
            on:change={(e) => updateEntity(kid.id, { reference_date: (e.target as HTMLInputElement).value })}
          />
          <button
            class="text-zinc-600 hover:text-rose-400 text-xs"
            on:click={() => deleteConfirm = { type: 'entity', id: kid.id, name: kid.name }}
            data-coco-desc={`Supprimer l'enfant ${kid.name}`}
          >✕</button>
        </div>

        <CostEventList
          events={kid.cost_events}
          entityAge={kid.current_age}
          on:change={(e) => updateCostEvents(kid.id, e.detail.events)}
          on:addCustom={() => addCustomEvent(kid.id, kid.cost_events)}
        />
      </div>
    {/each}

    {#if kids.length === 0 && !showKidForm}
      <p class="text-xs text-zinc-500 italic">{$_('life.no_items', 'Aucun élément ajouté')}</p>
    {/if}

    {#if showKidForm}
      <div class="flex items-end gap-2 mt-2">
        <input type="text" placeholder="Prénom" bind:value={newKidName} class="flex-1 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
        <input type="date" bind:value={newKidBirth} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
        <button class="bg-purple-600 text-white text-xs rounded px-3 py-1 hover:bg-purple-500" on:click={handleAddKid}>Ajouter</button>
        <button class="text-zinc-500 text-xs" on:click={() => showKidForm = false}>Annuler</button>
      </div>
    {:else}
      <button
        class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-purple-700/50 transition-colors mt-2"
        on:click={() => showKidForm = true}
        data-coco-desc="Ouvrir le formulaire d'ajout d'enfant"
      >
        + {$_('life.kids.add', 'Ajouter un enfant')}
      </button>
    {/if}
  </div>

  <!-- ── Pets ─────────────────────────────────────────────────────────────── -->
  <div
    class="bg-zinc-900/50 border border-emerald-800/30 rounded-xl p-4"
    data-coco-desc="Section animaux de compagnie. Chien, chat ou autre — chaque animal a des coûts vétérinaires et d'entretien qui évoluent avec l'âge."
  >
    <h3 class="text-sm font-semibold text-emerald-300 mb-1">{$_('life.pets.title', 'Animaux')} 🐾</h3>

    {#each pets as pet (pet.id)}
      <div class="bg-zinc-900/70 border border-zinc-800/50 rounded-lg p-3 mb-3" data-coco-desc={`Fiche animal : ${pet.name}, ${pet.current_age} ans`}>
        <div class="flex items-center gap-2 mb-2">
          <input
            type="text"
            value={pet.name}
            class="flex-1 bg-transparent text-zinc-200 text-sm font-medium focus:outline-none"
            on:blur={(e) => updateEntity(pet.id, { name: (e.target as HTMLInputElement).value })}
          />
          <select
            value={pet.metadata?.pet_type || 'dog'}
            class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-0.5 text-xs text-zinc-300"
            on:change={(e) => updateEntity(pet.id, { metadata: { ...pet.metadata, pet_type: (e.target as HTMLSelectElement).value } })}
          >
            <option value="dog">Chien</option>
            <option value="cat">Chat</option>
            <option value="other">Autre</option>
          </select>
          <span class="text-zinc-400 text-xs">{pet.current_age} ans</span>
          <input
            type="date"
            value={pet.reference_date}
            class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-0.5 text-xs text-zinc-300"
            on:change={(e) => updateEntity(pet.id, { reference_date: (e.target as HTMLInputElement).value })}
          />
          <button
            class="text-zinc-600 hover:text-rose-400 text-xs"
            on:click={() => deleteConfirm = { type: 'entity', id: pet.id, name: pet.name }}
          >✕</button>
        </div>

        <CostEventList
          events={pet.cost_events}
          entityAge={pet.current_age}
          on:change={(e) => updateCostEvents(pet.id, e.detail.events)}
          on:addCustom={() => addCustomEvent(pet.id, pet.cost_events)}
        />
      </div>
    {/each}

    {#if pets.length === 0 && !showPetForm}
      <p class="text-xs text-zinc-500 italic">{$_('life.no_items', 'Aucun élément ajouté')}</p>
    {/if}

    {#if showPetForm}
      <div class="flex items-end gap-2 mt-2">
        <input type="text" placeholder="Nom" bind:value={newPetName} class="flex-1 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
        <select bind:value={newPetType} class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200">
          <option value="dog">Chien</option>
          <option value="cat">Chat</option>
          <option value="other">Autre</option>
        </select>
        <input type="date" bind:value={newPetBirth} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
        <button class="bg-emerald-600 text-white text-xs rounded px-3 py-1 hover:bg-emerald-500" on:click={handleAddPet}>Ajouter</button>
        <button class="text-zinc-500 text-xs" on:click={() => showPetForm = false}>Annuler</button>
      </div>
    {:else}
      <button
        class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-emerald-700/50 transition-colors mt-2"
        on:click={() => showPetForm = true}
        data-coco-desc="Ouvrir le formulaire d'ajout d'animal"
      >
        + {$_('life.pets.add', 'Ajouter un animal')}
      </button>
    {/if}
  </div>

  <!-- ── Cars ─────────────────────────────────────────────────────────────── -->
  <div
    class="bg-zinc-900/50 border border-amber-800/30 rounded-xl p-4"
    data-coco-desc="Section véhicules. Chaque voiture a des coûts de carburant, d'assurance, d'entretien, de contrôle technique et de remplacement."
  >
    <h3 class="text-sm font-semibold text-amber-300 mb-1">{$_('life.cars.title', 'Véhicules')} 🚗</h3>

    {#each cars as car (car.id)}
      <div class="bg-zinc-900/70 border border-zinc-800/50 rounded-lg p-3 mb-3" data-coco-desc={`Fiche véhicule : ${car.name}, ${car.current_age} ans`}>
        <div class="flex flex-wrap items-center gap-2 mb-2">
          <input
            type="text"
            value={car.name}
            class="w-32 bg-transparent text-zinc-200 text-sm font-medium focus:outline-none"
            on:blur={(e) => updateEntity(car.id, { name: (e.target as HTMLInputElement).value })}
          />
          <select
            value={car.metadata?.fuel_type || 'petrol'}
            class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-0.5 text-xs text-zinc-300"
            on:change={(e) => updateEntity(car.id, { metadata: { ...car.metadata, fuel_type: (e.target as HTMLSelectElement).value } })}
          >
            <option value="petrol">Essence</option>
            <option value="diesel">Diesel</option>
            <option value="electric">Électrique</option>
            <option value="hybrid">Hybride</option>
          </select>
          <span class="text-zinc-400 text-xs">{car.current_age} ans</span>
          <input
            type="date"
            value={car.reference_date}
            class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-0.5 text-xs text-zinc-300 w-32"
            on:change={(e) => updateEntity(car.id, { reference_date: (e.target as HTMLInputElement).value })}
          />
          <button
            class="text-zinc-600 hover:text-rose-400 text-xs"
            on:click={() => deleteConfirm = { type: 'entity', id: car.id, name: car.name }}
          >✕</button>
        </div>

        <CostEventList
          events={car.cost_events}
          entityAge={car.current_age}
          on:change={(e) => updateCostEvents(car.id, e.detail.events)}
          on:addCustom={() => addCustomEvent(car.id, car.cost_events)}
        />
      </div>
    {/each}

    {#if cars.length === 0 && !showCarForm}
      <p class="text-xs text-zinc-500 italic">{$_('life.no_items', 'Aucun élément ajouté')}</p>
    {/if}

    {#if showCarForm}
      <div class="flex flex-wrap items-end gap-2 mt-2">
        <input type="text" placeholder="Nom" bind:value={newCarName} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
        <select bind:value={newCarFuel} class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200">
          <option value="petrol">Essence</option>
          <option value="diesel">Diesel</option>
          <option value="electric">Électrique</option>
          <option value="hybrid">Hybride</option>
        </select>
        <input type="date" bind:value={newCarDate} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
        <button class="bg-amber-600 text-white text-xs rounded px-3 py-1 hover:bg-amber-500" on:click={handleAddCar}>Ajouter</button>
        <button class="text-zinc-500 text-xs" on:click={() => showCarForm = false}>Annuler</button>
      </div>
    {:else}
      <button
        class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-amber-700/50 transition-colors mt-2"
        on:click={() => showCarForm = true}
        data-coco-desc="Ouvrir le formulaire d'ajout de véhicule"
      >
        + {$_('life.cars.add', 'Ajouter un véhicule')}
      </button>
    {/if}
  </div>

  <!-- ── Tech ──────────────────────────────────────────────────────────────── -->
  <div
    class="bg-zinc-900/50 border border-sky-800/30 rounded-xl p-4"
    data-coco-desc="Section appareils tech. Téléphone, ordinateur, tablette — chaque appareil a un cycle de remplacement et des coûts d'accessoires."
  >
    <h3 class="text-sm font-semibold text-sky-300 mb-1">{$_('life.tech.title', 'Tech')} 💻</h3>

    {#each tech as device (device.id)}
      <div class="bg-zinc-900/70 border border-zinc-800/50 rounded-lg p-3 mb-3" data-coco-desc={`Fiche appareil : ${device.name}, ${device.current_age} ans`}>
        <div class="flex items-center gap-2 mb-2">
          <input
            type="text"
            value={device.name}
            class="flex-1 bg-transparent text-zinc-200 text-sm font-medium focus:outline-none"
            on:blur={(e) => updateEntity(device.id, { name: (e.target as HTMLInputElement).value })}
          />
          <span class="text-zinc-400 text-xs">{device.current_age} ans</span>
          <input
            type="date"
            value={device.reference_date}
            class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-0.5 text-xs text-zinc-300 w-32"
            on:change={(e) => updateEntity(device.id, { reference_date: (e.target as HTMLInputElement).value })}
          />
          <button
            class="text-zinc-600 hover:text-rose-400 text-xs"
            on:click={() => deleteConfirm = { type: 'entity', id: device.id, name: device.name }}
          >✕</button>
        </div>

        <CostEventList
          events={device.cost_events}
          entityAge={device.current_age}
          on:change={(e) => updateCostEvents(device.id, e.detail.events)}
          on:addCustom={() => addCustomEvent(device.id, device.cost_events)}
        />
      </div>
    {/each}

    {#if tech.length === 0 && !showTechForm}
      <p class="text-xs text-zinc-500 italic">{$_('life.no_items', 'Aucun élément ajouté')}</p>
    {/if}

    {#if showTechForm}
      <div class="flex flex-wrap items-end gap-2 mt-2">
        <input type="text" placeholder="Nom" bind:value={newTechName} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
        <select bind:value={newTechType} class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200">
          <option value="phone">Téléphone</option>
          <option value="laptop">Ordinateur</option>
          <option value="tablet">Tablette</option>
        </select>
        <input type="date" bind:value={newTechDate} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
        <button class="bg-sky-600 text-white text-xs rounded px-3 py-1 hover:bg-sky-500" on:click={handleAddTech}>Ajouter</button>
        <button class="text-zinc-500 text-xs" on:click={() => showTechForm = false}>Annuler</button>
      </div>
    {:else}
      <button
        class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-sky-700/50 transition-colors mt-2"
        on:click={() => showTechForm = true}
        data-coco-desc="Ouvrir le formulaire d'ajout d'appareil"
      >
        + {$_('life.tech.add', 'Ajouter un appareil')}
      </button>
    {/if}
  </div>

  <!-- ── Recurring Expenses ────────────────────────────────────────────────── -->
  <div
    class="bg-zinc-900/50 border border-rose-800/30 rounded-xl p-4"
    data-coco-desc="Section dépenses récurrentes à durée limitée. Dépenses annuelles avec une date de début et de fin."
  >
    <h3 class="text-sm font-semibold text-rose-300 mb-1">{$_('life.recurring.title', 'Dépenses récurrentes à durée limitée')} 🔄</h3>
    <p class="text-[10px] text-zinc-500 mb-3">{$_('life.recurring.intro', 'Remboursements de prêt, colonies de vacances, sport enfant — ce qui revient chaque année mais a une date de fin.')}</p>

    {#each recurringExpenses as expense (expense.id)}
      <div class="flex items-end gap-2 mb-2" data-coco-desc={`Dépense récurrente : ${expense.label || 'Sans nom'}, ${expense.annual_amount}€/an de ${expense.from_year} à ${expense.to_year}`}>
        <input
          type="text"
          placeholder="Description"
          value={expense.label}
          class="flex-1 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200"
          on:blur={(e) => debouncedSaveRecurring(expense.id, 'label', (e.target as HTMLInputElement).value)}
        />
        <input
          type="number"
          step="0.01"
          min="0"
          value={parseFloat(expense.annual_amount) || 0}
          class="w-20 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200 text-right"
          on:blur={(e) => debouncedSaveRecurring(expense.id, 'annual_amount', parseFloat((e.target as HTMLInputElement).value) || 0)}
        />
        <span class="text-[10px] text-zinc-500">€/an</span>
        <input
          type="number"
          min="2000"
          max="2100"
          value={expense.from_year}
          class="w-16 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200"
          on:blur={(e) => debouncedSaveRecurring(expense.id, 'from_year', parseInt((e.target as HTMLInputElement).value) || 2026)}
        />
        <input
          type="number"
          min="2000"
          max="2100"
          value={expense.to_year}
          class="w-16 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200"
          on:blur={(e) => debouncedSaveRecurring(expense.id, 'to_year', parseInt((e.target as HTMLInputElement).value) || 2031)}
        />
        <button
          class="text-zinc-600 hover:text-rose-400 text-xs mb-1"
          on:click={() => deleteRecurring(expense.id)}
        >✕</button>
      </div>
    {/each}

    {#if recurringExpenses.length === 0}
      <p class="text-xs text-zinc-500 italic">{$_('life.no_items', 'Aucun élément ajouté')}</p>
    {/if}

    <button
      class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-rose-700/50 transition-colors mt-2"
      on:click={addRecurring}
      data-coco-desc="Ajouter une dépense récurrente à durée limitée"
    >
      + {$_('life.recurring.add', 'Ajouter')}
    </button>
  </div>
</div>

<!-- ── Delete confirmation modal ─────────────────────────────────────────── -->
{#if deleteConfirm}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" data-coco-desc="Confirmation de suppression">
    <div class="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-sm w-full mx-4">
      <p class="text-sm text-zinc-200 mb-2">{$_('life.delete_confirm', 'Supprimer définitivement')} <strong>{deleteConfirm.name}</strong> ?</p>
      <p class="text-xs text-zinc-500 mb-4">Cette action est irréversible.</p>
      <div class="flex justify-end gap-2">
        <button class="text-xs text-zinc-400 hover:text-zinc-200 px-3 py-1" on:click={() => deleteConfirm = null}>{$_('common.cancel', 'Annuler')}</button>
        <button
          class="text-xs bg-rose-600 text-white rounded px-3 py-1 hover:bg-rose-500"
          on:click={() => deleteEntity(deleteConfirm!.id)}
        >{$_('life.delete_confirm', 'Supprimer définitivement')}</button>
      </div>
    </div>
  </div>
{/if}