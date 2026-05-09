<script lang="ts">
	/**
	 * Revenue page — CA input, growth presets, 5-year preview, tax breaks.
	 *
	 * Stats row (CA/cotisations/net), CA input, 4-card growth preset grid,
	 * 5-year CA preview, CESU/charity tax credit inputs.
	 */
	import { api } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import type { PageData } from './$types';

	export let data: PageData;

	let profile = data.profile ?? {};
	let growthPresets = data.growthPresets ?? {};
	let stats = data.stats ?? { grossMonthly: 0, cotisationsMonthly: 0, netMonthly: 0, aeRate: '0.262' };

	// ── Auto-save ───────────────────────────────────────────────────────────
	const DEBOUNCE_MS = 800;
	let saveIndicator: 'idle' | 'saving' | 'saved' | 'error' = 'idle';

	async function autoSave(field: string, value: unknown) {
		saveIndicator = 'saving';
		try {
			const updated = await api.put('/profile', { [field]: value });
			profile = updated;
			// Recompute stats
			if (field === 'monthly_gross_ca' && value) {
				const ca = parseFloat(String(value));
				const rate = parseFloat(stats.aeRate);
				stats = {
					grossMonthly: ca,
					cotisationsMonthly: Math.round(ca * rate * 100) / 100,
					netMonthly: Math.round((ca - ca * rate) * 100) / 100,
					aeRate: stats.aeRate,
				};
			}
			saveIndicator = 'saved';
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[revenue] Save failed:', err);
			saveIndicator = 'error';
		}
	}

	let timers: Record<string, ReturnType<typeof setTimeout>> = {};
	function debouncedSave(field: string, value: unknown) {
		clearTimeout(timers[field]);
		saveIndicator = 'saving';
		timers[field] = setTimeout(() => autoSave(field, value), DEBOUNCE_MS);
	}

	// ── Growth preset selection ─────────────────────────────────────────────
	async function selectPreset(key: string) {
		profile.growth_preset = key;
		await autoSave('growth_preset', key);
	}

	// ── 5-year preview (client-side — trivial math) ─────────────────────────
	$: effectiveRate = profile.growth_preset === 'custom'
		? Number(profile.growth_rate_custom) || 0.03
		: (growthPresets[profile.growth_preset]?.rate
			? parseFloat(growthPresets[profile.growth_preset].rate)
			: 0.03);

	$: monthlyCA = profile.monthly_gross_ca ? parseFloat(profile.monthly_gross_ca) : 0;
	$: fiveYearPreview = Array.from({ length: 5 }, (_, i) =>
		Math.round(monthlyCA * Math.pow(1 + effectiveRate, i) * 100) / 100
	);

	// ── CESU / Charity helpers ──────────────────────────────────────────────
	$: cesuAnnual = profile.cesu_annual ? parseFloat(profile.cesu_annual) : 0;
	$: charityAnnual = profile.charity_annual ? parseFloat(profile.charity_annual) : 0;
	$: cesuCredit = Math.min(cesuAnnual * 0.5, 6000);
	$: charityCredit = Math.min(charityAnnual * 0.66, 20000);

	// ── Formatting ──────────────────────────────────────────────────────────
	function fmt(n: number): string {
		return n.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + '€';
	}
	function fmtDec(n: number): string {
		return n.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + '€';
	}
	function pctStr(rate: any): string {
		const r = typeof rate === 'string' ? parseFloat(rate) : rate;
		return (r * 100).toFixed(0) + '%';
	}

	// ── Stat card colors ───────────────────────────────────────────────────
	const statCards = [
		{ label: 'CA brut / mois', value: fmtDec(stats.grossMonthly), accent: 'teal', sub: '' },
		{ label: 'Cotisations / mois', value: fmtDec(stats.cotisationsMonthly), accent: 'rose', sub: `${pctStr(stats.aeRate)}` },
		{ label: 'Net après cotisations', value: fmtDec(stats.netMonthly), accent: 'emerald', sub: '' },
	];

	$: indicatorText = saveIndicator === 'saved' ? '✓ Enregistré'
		: saveIndicator === 'saving' ? '↻ Enregistrement...'
		: saveIndicator === 'error' ? '✗ Erreur' : '';
</script>

<svelte:head>
	<title>Revenus — Horizon</title>
</svelte:head>

<div class="space-y-5">
	<div class="flex items-center justify-end gap-2 h-4">
		<span class="text-[10px] {saveIndicator === 'saved' ? 'text-emerald-400' : saveIndicator === 'error' ? 'text-rose-400' : 'text-zinc-500'}">{indicatorText}</span>
	</div>

	<!-- Stats Row -->
	<div class="grid grid-cols-3 gap-3">
		{#each statCards as card}
			<div class="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-3 text-center">
				{#if card.sub}
					<span class="text-[9px] text-zinc-500 block">{card.sub}</span>
				{/if}
				<span class="text-lg font-bold font-mono text-{card.accent}-300 block">{card.value}</span>
				<span class="text-[10px] text-zinc-400">{card.label}</span>
			</div>
		{/each}
	</div>

	<!-- CA Input -->
	<Card title="Chiffre d'affaires" icon="💰" accent="teal" dataCocoDesc="Saisie du chiffre d'affaires brut mensuel">
		<div class="flex items-end gap-3">
			<label class="flex flex-col gap-1.5 flex-1">
				<span class="text-[11px] text-zinc-400 font-medium">CA brut mensuel (€)</span>
				<input
					type="number"
					min="0"
					step="100"
					value={monthlyCA || ''}
					placeholder="ex: 5000"
					oninput={(e) => {
						const val = parseFloat((e.target as HTMLInputElement).value);
						if (!isNaN(val) && val >= 0) debouncedSave('monthly_gross_ca', val);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-sm font-mono text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full"
				/>
			</label>
		</div>
	</Card>

	<!-- Growth Presets -->
	<Card title="Croissance annuelle" icon="📈" accent="emerald" dataCocoDesc="Sélecteur de projection de croissance du CA">
		<p class="text-[11px] text-zinc-400 mb-3">Comment votre CA va évoluer ?</p>
		<div class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
			{#each Object.entries(growthPresets) as [key, preset]}
				{@const p = preset as any}
				<button
					onclick={() => selectPreset(key)}
					class="text-left rounded-lg p-3 border transition-all
						{profile.growth_preset === key
							? 'border-teal-500/60 bg-teal-950/20'
							: 'border-zinc-700/30 bg-zinc-900/30 hover:border-zinc-600/40'}"
				>
					<span class="block text-[11px] font-medium text-zinc-200">{p.label}</span>
					{#if p.rate}
						<span class="block text-sm font-mono text-emerald-300 font-bold">{pctStr(p.rate)}</span>
					{:else}
						<span class="block text-[10px] text-zinc-500">personnalisé</span>
					{/if}
					<span class="block text-[9px] text-zinc-500 mt-1 leading-tight">{p.description}</span>
				</button>
			{/each}
		</div>

		{#if profile.growth_preset === 'custom'}
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Taux personnalisé (%)</span>
				<input
					type="number"
					min="0"
					max="50"
					step="0.5"
					value={(Number(profile.growth_rate_custom) || 0.03) * 100}
					oninput={(e) => {
						const val = parseFloat((e.target as HTMLInputElement).value) / 100;
						if (!isNaN(val) && val >= 0) debouncedSave('growth_rate_custom', val);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-sm font-mono text-zinc-200 focus:outline-none focus:border-teal-500/60 w-32"
				/>
			</label>
		{/if}

		<!-- 5-year preview -->
		{#if monthlyCA > 0}
			<div class="mt-4 p-3 rounded-lg bg-zinc-900/30 border border-zinc-800/30">
				<p class="text-[10px] text-zinc-500 mb-2">Projection sur 5 ans</p>
				<div class="flex gap-2">
					{#each fiveYearPreview as val, i}
						<div class="flex-1 text-center bg-zinc-800/40 rounded-lg py-2 px-1">
							<span class="block text-[9px] text-zinc-500">2026+{i}</span>
							<span class="block text-[11px] font-mono text-teal-300 font-semibold">{fmtDec(val)}</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</Card>

	<!-- Tax breaks -->
	<Card title="Avantages fiscaux" icon="🏷️" accent="purple" dataCocoDesc="Crédits d'impôt CESU et dons aux associations">
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">CESU annuel (€)</span>
				<input
					type="number" min="0" step="100"
					value={cesuAnnual || ''} placeholder="0"
					oninput={(e) => {
						const val = parseFloat((e.target as HTMLInputElement).value) || 0;
						debouncedSave('cesu_annual', val);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-sm font-mono text-zinc-200 focus:outline-none focus:border-purple-500/60 w-full"
				/>
				<span class="text-[10px] text-purple-400">Crédit d'impôt 50% → économie {fmtDec(cesuCredit)}€/an</span>
			</label>
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Dons annuels (€)</span>
				<input
					type="number" min="0" step="100"
					value={charityAnnual || ''} placeholder="0"
					oninput={(e) => {
						const val = parseFloat((e.target as HTMLInputElement).value) || 0;
						debouncedSave('charity_annual', val);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-sm font-mono text-zinc-200 focus:outline-none focus:border-purple-500/60 w-full"
				/>
				<span class="text-[10px] text-purple-400">Réduction 66% → économie {fmtDec(charityCredit)}€/an</span>
			</label>
		</div>
	</Card>
</div>