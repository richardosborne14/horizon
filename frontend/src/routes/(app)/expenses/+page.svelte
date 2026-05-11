<script lang="ts">
	/**
	 * Expenses page — 12-category expense grid, inflation preview, and loans section.
	 * TASK-6.3: Loans management section added below the expense grid.
	 */
	import { api } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import type { PageData } from './$types';

	export let data: PageData;

	let expenses = data.expenses ?? {};
	let labels = data.labels ?? {};
	let total = data.total ?? '0';
	let preview = data.inflationPreview ?? {};
	let customExpenses = (data as any).customExpenses ?? [];
	let loans = (data as any).loans ?? [];
	let expenseTimeline = (data as any).expenseTimeline ?? null;

	// ── Custom expense CRUD (TASK-7.3) ─────────────────────────────────────
	let customDebounce: ReturnType<typeof setTimeout>;

	function addCustomExpense() {
		customExpenses = [...customExpenses, {
			id: 'ce_' + Math.random().toString(36).slice(2, 8),
			label: '',
			amount: 0,
		}];
		onCustomChange();
	}

	function removeCustomExpense(index: number) {
		customExpenses = customExpenses.filter((_: any, i: number) => i !== index);
		onCustomChange();
	}

	function onCustomChange() {
		clearTimeout(customDebounce);
		customDebounce = setTimeout(() => saveCustomExpenses(), DEBOUNCE_MS);
	}

	function onCustomLabelInput(e: Event, idx: number) {
		customExpenses[idx].label = (e.target as HTMLInputElement).value;
		onCustomChange();
	}

	function onCustomAmountInput(e: Event, idx: number) {
		customExpenses[idx].amount = parseFloat((e.target as HTMLInputElement).value) || 0;
		onCustomChange();
	}

	async function saveCustomExpenses() {
		saveIndicator = 'saving';
		try {
			// Save custom_expenses via PUT /api/profile
			const res = await api.put('/profile', {
				custom_expenses: customExpenses.map((ce: any) => ({
					id: ce.id,
					label: ce.label || 'Sans nom',
					amount: String(ce.amount || 0),
				})),
			});
			// Re-fetch total which now includes custom expenses
			const expensesRes = await api.get<{ total: string; custom_expenses: any[] }>('/profile/expenses');
			total = expensesRes.total;
			customExpenses = expensesRes.custom_expenses ?? [];
			const prev = await api.get<{ preview: any }>('/profile/expenses/inflation-preview');
			preview = prev.preview ?? {};
			saveIndicator = 'saved';
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[expenses] Custom save failed:', err);
			saveIndicator = 'error';
		}
	}

	// ── Expense categories (ordered for grid) ──────────────────────────────
	const categories = [
		'loyer', 'energie', 'internet', 'assurance',
		'transport', 'alimentation', 'sante', 'loisirs',
		'abonnements', 'impots', 'credit', 'divers',
	];

	// ── Auto-save with debounce ──────────────────────────────────────────
	const DEBOUNCE_MS = 800;
	let saveIndicator: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
	let debounceTimer: ReturnType<typeof setTimeout>;

	async function saveExpenses(expObj: Record<string, any>) {
		saveIndicator = 'saving';
		try {
			const res = await api.put<{ total: string }>('/profile/expenses', expObj);
			total = res.total;
			const prev = await api.get<{ preview: any }>('/profile/expenses/inflation-preview');
			preview = prev.preview ?? {};
			saveIndicator = 'saved';
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[expenses] Save failed:', err);
			saveIndicator = 'error';
		}
	}

	function onExpenseChange(category: string, value: number) {
		const updated = { ...expenses, [category]: String(value) };
		expenses = updated;
		clearTimeout(debounceTimer);
		saveIndicator = 'saving';
		debounceTimer = setTimeout(() => saveExpenses(updated), DEBOUNCE_MS);
	}

	// ── Inflation preview helpers ────────────────────────────────────────
	const scaleEmojis: Record<string, string> = {
		optimistic: '☀️', moderate: '⛅', pessimistic: '🌧️',
	};
	const scaleColors: Record<string, string> = {
		optimistic: 'text-emerald-400', moderate: 'text-amber-400', pessimistic: 'text-rose-400',
	};
	const horizons = ['5', '10', '20', '30'];

	function fmtVal(v: string): string {
		const n = parseFloat(v);
		return n.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + '€';
	}

	$: indicatorText = saveIndicator === 'saved' ? '✓ Enregistré'
		: saveIndicator === 'saving' ? '↻ Enregistrement...'
		: saveIndicator === 'error' ? '✗ Erreur' : '';

	// ── Loans CRUD (TASK-6.3) ────────────────────────────────────────────
	let showLoanForm = false;
	let newLoanLabel = '';
	let newLoanType = 'mortgage';
	let newLoanMonthly = 0;
	let newLoanStartDate = new Date().toISOString().substring(0, 10);
	let newLoanEndDate = '';
	let newLoanRemainingMonths = 0;
	let newLoanRemainingBalance = 0;
	let newLoanInsurance = 0;

	async function addLoan() {
		if (!newLoanLabel || newLoanMonthly <= 0) return;
		const payload: Record<string, any> = {
			label: newLoanLabel,
			loan_type: newLoanType,
			monthly_payment: newLoanMonthly,
			start_date: newLoanStartDate,
		};
		if (newLoanEndDate) payload.end_date = newLoanEndDate;
		else if (newLoanRemainingMonths > 0) payload.remaining_months = newLoanRemainingMonths;
		if (newLoanRemainingBalance > 0) payload.remaining_balance = newLoanRemainingBalance;
		if (newLoanInsurance > 0) payload.insurance_monthly = newLoanInsurance;

		try {
			const loan = await api.post('/loans', payload);
			if (loan) loans = [...loans, loan];
			newLoanLabel = '';
			newLoanMonthly = 0;
			newLoanRemainingMonths = 0;
			newLoanRemainingBalance = 0;
			newLoanInsurance = 0;
			showLoanForm = false;
		} catch (err) {
			console.error('[expenses] Loan create failed:', err);
		}
	}

	async function deleteLoan(id: string) {
		try {
			await api.delete(`/loans/${id}`);
			loans = loans.filter((l: any) => l.id !== id);
		} catch (err) {
			console.error('[expenses] Loan delete failed:', err);
		}
	}

	const loanTypeLabels: Record<string, string> = {
		mortgage: 'Immobilier', auto: 'Auto', consumer: 'Conso',
		student: 'Étudiant', business: 'Pro', other: 'Autre',
	};

	function fmtDate(d: string | null): string {
		if (!d) return '—';
		return d.substring(0, 10);
	}

	$: loansTotalMonthly = loans.reduce((sum: number, l: any) =>
		sum + parseFloat(l.monthly_payment || '0') + parseFloat(l.insurance_monthly || '0'), 0);
</script>

<svelte:head>
	<title>Charges — Horizon</title>
</svelte:head>

<div class="space-y-5">
	<div class="flex items-center justify-end gap-2 h-4">
		<span class="text-[10px] {saveIndicator === 'saved' ? 'text-emerald-400' : saveIndicator === 'error' ? 'text-rose-400' : 'text-zinc-500'}">{indicatorText}</span>
	</div>

	<!-- Stats Row -->
	<div class="grid grid-cols-2 gap-3">
		<div class="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-3 text-center">
			<span class="text-lg font-bold font-mono text-amber-300 block">{fmtVal(total)}</span>
			<span class="text-[10px] text-zinc-400">Total mensuel (base 2026)</span>
		</div>
		<div class="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-3 text-center">
			<span class="text-lg font-bold font-mono text-amber-300 block">{fmtVal(String(parseFloat(total) * 12))}</span>
			<span class="text-[10px] text-zinc-400">Total annuel</span>
		</div>
	</div>

	<!-- Expense Input Grid -->
	<Card title="Dépenses mensuelles" icon="📋" accent="amber" dataCocoDesc="Grille des 12 catégories de dépenses mensuelles">
		<p class="text-[11px] text-zinc-400 mb-3">Saisissez vos dépenses actuelles. L'inflation est appliquée automatiquement dans l'onglet Horizon.</p>
		<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
			{#each categories as cat}
				<label class="flex flex-col gap-1">
					<span class="text-[10px] text-zinc-500">{labels[cat] || cat}</span>
					<div class="relative">
						<input
							type="number"
							min="0"
							step="10"
							value={expenses[cat] ? parseFloat(expenses[cat]) : ''}
							placeholder="0"
							oninput={(e) => {
								const val = parseFloat((e.target as HTMLInputElement).value) || 0;
								onExpenseChange(cat, val);
							}}
							class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg pl-3 pr-8 py-2 text-xs font-mono text-zinc-200 focus:outline-none focus:border-amber-500/60 w-full"
						/>
						<span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-zinc-600">€/mois</span>
					</div>
				</label>
			{/each}
		</div>
	</Card>

	<!-- Custom Expenses (TASK-7.3) -->
	<Card title="Autres dépenses mensuelles" icon="✚" accent="sky" dataCocoDesc="Dépenses personnalisées qui ne rentrent pas dans les 12 catégories standard">
		<p class="text-[11px] text-zinc-400 mb-3">Dépenses qui ne rentrent pas dans les catégories ci-dessus : coworking, aide ménagère, abonnements pro, etc.</p>

		{#each customExpenses as expense, i (expense.id)}
			<div class="flex items-end gap-2 mb-2">
				<input type="text" value={expense.label} placeholder="Description"
					oninput={(e) => onCustomLabelInput(e, i)}
					class="flex-1 bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200" />
				<div class="relative w-28">
					<input type="number" value={expense.amount} min="0" step="10"
						oninput={(e) => onCustomAmountInput(e, i)}
						class="w-full bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 pr-8" />
					<span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-zinc-500">€/m</span>
				</div>
				<button class="text-zinc-600 hover:text-rose-400 text-sm mb-1"
					onclick={() => removeCustomExpense(i)}>✕</button>
			</div>
		{/each}

		<button onclick={addCustomExpense}
			class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-sky-700/50 transition-colors mt-1">
			+ Ajouter une dépense
		</button>
	</Card>

	<!-- Loans Section (TASK-6.3) -->
	<Card title="Crédits & Emprunts" icon="🏦" accent="purple" dataCocoDesc="Section des crédits et emprunts avec dates de fin. Les mensualités ne sont pas indexées sur l'inflation.">
		<p class="text-[11px] text-zinc-400 mb-3">Détaillez vos emprunts avec leur date de fin pour une projection précise. Les mensualités sont fixes (pas d'inflation).</p>

		{#if loans.length > 0}
			<div class="flex items-center gap-2 mb-3 p-2 bg-purple-950/20 border border-purple-800/20 rounded-lg">
				<span class="text-xs font-mono text-purple-300 font-bold">{fmtVal(String(loansTotalMonthly))}</span>
				<span class="text-[10px] text-zinc-500">/ mois de remboursements</span>
			</div>

			<div class="space-y-2">
				{#each loans as loan (loan.id)}
					<div class="flex items-center gap-2 p-2 bg-zinc-900/60 border border-zinc-700/30 rounded-lg" data-coco-desc="Crédit {loan.label} : {loan.monthly_payment}€/mois{loan.end_date ? ', fin le ' + loan.end_date : ''}">
						<span class="text-xs text-zinc-300 flex-1">{loan.label}</span>
						<span class="text-[10px] text-zinc-500 bg-zinc-800/40 px-1.5 py-0.5 rounded">{loanTypeLabels[loan.loan_type] || loan.loan_type}</span>
						<span class="text-xs font-mono text-zinc-200 w-20 text-right">{parseFloat(loan.monthly_payment || '0').toLocaleString('fr-FR')}€</span>
						<span class="text-[10px] text-zinc-500 w-24 text-right">{loan.end_date ? fmtDate(loan.end_date) : 'Sans fin'}</span>
						<button
							class="text-zinc-600 hover:text-rose-400 text-xs"
							onclick={() => deleteLoan(loan.id)}
							data-coco-desc="Supprimer le crédit {loan.label}"
						>✕</button>
					</div>
				{/each}
			</div>
		{:else}
			<p class="text-xs text-zinc-500 italic mb-2">Aucun emprunt enregistré. Ajoutez vos crédits pour une projection plus précise.</p>
		{/if}

		{#if showLoanForm}
			<div class="flex flex-wrap items-end gap-2 mt-3 p-3 bg-zinc-900/40 border border-zinc-700/30 rounded-lg">
				<input type="text" placeholder="Libellé" bind:value={newLoanLabel} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
				<select bind:value={newLoanType} class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200">
					<option value="mortgage">Immobilier</option>
					<option value="auto">Auto</option>
					<option value="consumer">Conso</option>
					<option value="student">Étudiant</option>
					<option value="business">Pro</option>
					<option value="other">Autre</option>
				</select>
				<input type="number" min="0" step="10" placeholder="€/mois" bind:value={newLoanMonthly} class="w-20 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
				<input type="date" bind:value={newLoanStartDate} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
				<input type="date" placeholder="Fin (optionnel)" bind:value={newLoanEndDate} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
				<button class="bg-purple-600 text-white text-xs rounded px-3 py-1 hover:bg-purple-500" onclick={addLoan}>Ajouter</button>
				<button class="text-zinc-500 text-xs" onclick={() => showLoanForm = false}>Annuler</button>
			</div>
		{:else}
			<button
				class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-purple-700/50 transition-colors mt-2"
				onclick={() => showLoanForm = true}
				data-coco-desc="Ouvrir le formulaire d'ajout d'emprunt"
			>
				+ Ajouter un emprunt
			</button>
		{/if}
	</Card>

	<!-- Sprint 6: Expense Evolution Timeline (TASK-6.6) -->
	{#if expenseTimeline?.timeline?.length}
		<Card title="Évolution des dépenses" icon="📊" accent="sky" dataCocoDesc="Évolution des dépenses mois par mois sur la durée de la projection. Montre quand les crédits se terminent, les enfants deviennent indépendants, etc.">
			<p class="text-[11px] text-zinc-400 mb-3">Comment vos dépenses évoluent dans le temps. Les barres empilées montrent la composition mensuelle.</p>

			<div class="space-y-1 max-h-64 overflow-y-auto">
				{#each expenseTimeline.timeline.slice(0, 30) as t}
					{@const year = t as any}
					{@const base = parseFloat(year.base_expenses_monthly || '0')}
					{@const loan = parseFloat(year.loan_payments_monthly || '0')}
					{@const kid = parseFloat(year.kid_expenses_monthly || '0')}
					{@const pet = parseFloat(year.pet_expenses_monthly || '0')}
					{@const car = parseFloat(year.car_expenses_monthly || '0')}
					{@const tech = parseFloat(year.tech_expenses_monthly || '0')}
					{@const total = base + loan + kid + pet + car + tech}
					<div class="flex items-center gap-2 py-1 border-b border-zinc-800/20 text-[10px]">
						<span class="w-10 text-zinc-500">{year.year}</span>
						<div class="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden flex">
							{#if base > 0}<div class="h-full bg-zinc-500" style="width: {(base / Math.max(1, total)) * 100}%"></div>{/if}
							{#if loan > 0}<div class="h-full bg-amber-500" style="width: {(loan / Math.max(1, total)) * 100}%"></div>{/if}
							{#if kid > 0}<div class="h-full bg-purple-500" style="width: {(kid / Math.max(1, total)) * 100}%"></div>{/if}
							{#if pet > 0}<div class="h-full bg-rose-400" style="width: {(pet / Math.max(1, total)) * 100}%"></div>{/if}
							{#if car > 0}<div class="h-full bg-sky-500" style="width: {(car / Math.max(1, total)) * 100}%"></div>{/if}
							{#if tech > 0}<div class="h-full bg-teal-500" style="width: {(tech / Math.max(1, total)) * 100}%"></div>{/if}
						</div>
						<span class="w-16 text-right font-mono text-zinc-300">{fmtVal(String(total))}</span>
					</div>
				{/each}
			</div>

			<div class="flex flex-wrap gap-3 mt-3 text-[9px] text-zinc-500">
				<span><span class="inline-block w-2 h-2 rounded bg-zinc-500 mr-1"></span>Base</span>
				<span><span class="inline-block w-2 h-2 rounded bg-amber-500 mr-1"></span>Crédits</span>
				<span><span class="inline-block w-2 h-2 rounded bg-purple-500 mr-1"></span>Enfants</span>
				<span><span class="inline-block w-2 h-2 rounded bg-rose-400 mr-1"></span>Animaux</span>
				<span><span class="inline-block w-2 h-2 rounded bg-sky-500 mr-1"></span>Véhicules</span>
				<span><span class="inline-block w-2 h-2 rounded bg-teal-500 mr-1"></span>Tech</span>
			</div>
		</Card>

		<!-- Key Expense Events -->
		{#if expenseTimeline.key_events?.length}
			<Card title="Événements à venir" icon="📅" accent="rose" dataCocoDesc="Événements clés du cycle de vie qui impactent vos dépenses mensuelles : fin de crédit, indépendance des enfants, fin de vie d'un animal.">
				<div class="space-y-2">
					{#each expenseTimeline.key_events as evt}
						{@const e = evt as any}
						{@const impact = parseFloat(e.impact_monthly || '0')}
						<div class="flex items-center gap-2 p-2 rounded-lg bg-zinc-900/40 border border-zinc-800/30" data-coco-desc={`Événement ${e.category} : ${e.event} en ${e.year}`}>
							<span class="text-[10px] w-12 text-zinc-500 font-mono">{e.year}</span>
							<span class="text-[11px] text-zinc-300 flex-1">{e.event}</span>
							<span class="text-[10px] font-mono {impact < 0 ? 'text-emerald-400' : 'text-rose-400'}">
								{impact < 0 ? '' : '+'}{fmtVal(String(impact))}/mois
							</span>
						</div>
					{/each}
				</div>
			</Card>
		{/if}
	{/if}

	<!-- Inflation Preview -->
	{#if Object.keys(preview).length > 0}
		<Card title="Impact de l'inflation" icon="📊" accent="rose" dataCocoDesc="Tableau de projection de l'inflation sur 5/10/20/30 ans selon 3 scénarios économiques">
			<div class="space-y-2">
				<div class="flex items-center gap-3 px-2 mb-1">
					<span class="w-28"></span>
					{#each horizons as h}
						<span class="flex-1 text-center text-[9px] text-zinc-600">+{h} ans</span>
					{/each}
				</div>
				{#each Object.entries(preview) as [scaleKey, scaleData]}
					{@const data = scaleData as Record<string, string>}
					<div class="flex items-center gap-3 px-2 py-2 rounded-lg bg-zinc-800/20">
						<span class="w-28 text-[10px] text-zinc-400 flex items-center gap-1">
							<span>{scaleEmojis[scaleKey] || ''}</span>
							{scaleKey === 'optimistic' ? 'Optimiste' : scaleKey === 'moderate' ? 'Modéré' : 'Pessimiste'}
						</span>
						{#each horizons as h}
							<span class="flex-1 text-center text-[11px] font-mono {scaleColors[scaleKey] || 'text-zinc-300'} font-semibold">
								{fmtVal(data[h] || '0')}
							</span>
						{/each}
					</div>
				{/each}
			</div>
		</Card>
	{/if}
</div>