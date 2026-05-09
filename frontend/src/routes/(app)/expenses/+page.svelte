<script lang="ts">
	/**
	 * Expenses page — 12-category expense grid with inflation preview table.
	 *
	 * Users enter their 2026 monthly expenses. The inflation preview table
	 * shows how costs grow over 5/10/20/30 years under 3 economic scenarios.
	 */
	import { api } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import type { PageData } from './$types';

	export let data: PageData;

	let expenses = data.expenses ?? {};
	let labels = data.labels ?? {};
	let total = data.total ?? '0';
	let preview = data.inflationPreview ?? {};

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
			// Re-fetch inflation preview
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