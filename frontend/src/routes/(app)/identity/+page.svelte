<script lang="ts">
	/**
	 * Identity page — user financial profile setup.
	 *
	 * Two cards: "Vous" (age, target, tax parts) and "Statut & Activité"
	 * (status, AE type, VL toggle, rate schedule preview).
	 * All fields auto-save after 800ms debounce via PUT /api/profile.
	 */
	import { api } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import type { PageData } from './$types';

	export let data: PageData;

	// ── Local state synced from server data ──────────────────────────────────
	let profile = data.profile ?? {};
	let rateSchedule = data.rateSchedule ?? [];
	let allSchedules = data.allSchedules ?? {};

	// Status options
	const statusOptions = [
		{ value: 'ae', label: 'Auto-entrepreneur (AE)' },
		{ value: 'eirl', label: 'EIRL' },
		{ value: 'eurl', label: 'EURL' },
		{ value: 'sasu', label: 'SASU' },
	];

	const aeTypeOptions = [
		{ value: 'bnc_non_reglementee', label: 'BNC non réglementée (ex: conseil, formation) — ~26.2%' },
		{ value: 'bic_services', label: 'BIC services (ex: coiffure, artisanat) — ~23.7%' },
		{ value: 'bic_vente', label: 'BIC vente — ~14.8%' },
		{ value: 'bnc_cipav', label: 'BNC CIPAV (profession libérale) — ~25.4%' },
	];

	// ── Save indicator ──────────────────────────────────────────────────────
	let saveIndicator: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
	let saveTimeout: ReturnType<typeof setTimeout>;
	const DEBOUNCE_MS = 800;
	const INDICATOR_DURATION_MS = 1500;

	function triggerSaveIndicator() {
		saveIndicator = 'saved';
		clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => {
			saveIndicator = 'idle';
		}, INDICATOR_DURATION_MS);
	}

	// ── Auto-save ───────────────────────────────────────────────────────────
	async function autoSave(field: string, value: unknown) {
		saveIndicator = 'saving';
		try {
			const updated = await api.put('/profile', { [field]: value });
			profile = updated;
			saveIndicator = 'saved';
			triggerSaveIndicator();
		} catch (err) {
			console.error('[identity] Save failed:', err);
			saveIndicator = 'error';
		}
	}

	// Debounced auto-save for text/number inputs
	let debounceTimers: Record<string, ReturnType<typeof setTimeout>> = {};

	function debouncedSave(field: string, value: unknown) {
		clearTimeout(debounceTimers[field]);
		saveIndicator = 'saving';
		debounceTimers[field] = setTimeout(() => autoSave(field, value), DEBOUNCE_MS);
	}

	// Immediate save for selects/toggles
	async function immediateSave(field: string, value: unknown) {
		clearTimeout(debounceTimers[field]);
		await autoSave(field, value);
	}

	// Fetch rate schedule when AE type changes
	async function onAeTypeChange(newType: string) {
		profile.ae_activity_type = newType;
		await autoSave('ae_activity_type', newType);
		// Re-fetch schedule for new type
		try {
			const resp = await api.get<{ schedule: Array<{ from_year: number; rate: string }> }>(
				'/rates/ae-schedule', { type: newType }
			);
			rateSchedule = resp.schedule;
		} catch (err) {
			console.error('[identity] Failed to fetch rate schedule:', err);
		}
	}

	// ── Formatting helpers ──────────────────────────────────────────────────
	function formatPercent(rateStr: string): string {
		const pct = parseFloat(rateStr) * 100;
		return pct.toFixed(1) + '%';
	}

	function formatAge(): string {
		if (profile.current_age == null) return '—';
		return `${profile.current_age} ans`;
	}

	function formatRunway(): string {
		if (profile.current_age == null || !profile.target_retirement_age) return '';
		const years = profile.target_retirement_age - profile.current_age;
		if (years <= 0) return 'Déjà atteint';
		return `${years} ans de runway`;
	}

	function formatDateValue(dateStr: string | null): string {
		if (!dateStr) return '';
		return dateStr.substring(0, 10);
	}

	// Computed classes
	$: indicatorClass = saveIndicator === 'saved'
		? 'text-emerald-400'
		: saveIndicator === 'error'
			? 'text-rose-400'
			: 'text-zinc-500';

	$: indicatorText = saveIndicator === 'saved'
		? '✓ Enregistré'
		: saveIndicator === 'saving'
			? '↻ Enregistrement...'
			: saveIndicator === 'error'
				? '✗ Erreur'
				: '';
</script>

<svelte:head>
	<title>Identité — Horizon</title>
</svelte:head>

<div class="space-y-5">
	<!-- Save indicator -->
	<div class="flex items-center justify-end gap-2 h-4">
		<span class="text-[10px] {indicatorClass} transition-colors duration-300">{indicatorText}</span>
	</div>

	<!-- Card 1: Vous -->
	<Card title="Vous" icon="👤" accent="teal" dataCocoDesc="Carte identité personnelle : âge, objectif de retraite, parts fiscales">
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
			<!-- Birth date -->
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Date de naissance</span>
				<input
					type="date"
					value={formatDateValue(profile.birth_date)}
					onchange={(e) => {
						const val = (e.target as HTMLInputElement).value;
						debouncedSave('birth_date', val || null);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-teal-500/60 focus:ring-1 focus:ring-teal-500/20 w-full"
				/>
				<span class="text-[10px] text-zinc-500">Âge actuel : {formatAge()}</span>
			</label>

			<!-- Target retirement age -->
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Âge de retraite cible</span>
				<input
					type="number"
					min="50"
					max="85"
					value={profile.target_retirement_age ?? 67}
					oninput={(e) => {
						const val = parseInt((e.target as HTMLInputElement).value);
						if (val >= 50 && val <= 85) debouncedSave('target_retirement_age', val);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-teal-500/60 focus:ring-1 focus:ring-teal-500/20 w-full"
				/>
				<span class="text-[10px] text-zinc-500">{formatRunway()}</span>
			</label>

			<!-- Tax parts -->
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Parts fiscales</span>
				<input
					type="number"
					min="1"
					max="10"
					step="0.5"
					value={profile.tax_parts ?? '1.0'}
					oninput={(e) => {
						const val = parseFloat((e.target as HTMLInputElement).value);
						if (val >= 1) debouncedSave('tax_parts', val);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-teal-500/60 focus:ring-1 focus:ring-teal-500/20 w-full"
				/>
				<span class="text-[10px] text-zinc-500">1=célibataire · 2=couple · +0.5/enfant</span>
			</label>
		</div>
	</Card>

	<!-- Card 2: Statut & Activité -->
	<Card title="Statut & Activité" icon="⚖️" accent="amber" dataCocoDesc="Statut juridique, type d'activité AE, versement libératoire et historique des taux de cotisation">
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
			<!-- Status -->
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Statut juridique</span>
				<select
					value={profile.status ?? 'ae'}
					onchange={async (e) => {
						const val = (e.target as HTMLSelectElement).value;
						await immediateSave('status', val);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-amber-500/60 focus:ring-1 focus:ring-amber-500/20 w-full"
				>
					{#each statusOptions as opt}
						<option value={opt.value}>{opt.label}</option>
					{/each}
				</select>
			</label>

			<!-- AE Activity Type -->
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Type d'activité AE</span>
				<select
					value={profile.ae_activity_type ?? 'bnc_non_reglementee'}
					onchange={async (e) => {
						const val = (e.target as HTMLSelectElement).value;
						await onAeTypeChange(val);
					}}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-amber-500/60 focus:ring-1 focus:ring-amber-500/20 w-full"
				>
					{#each aeTypeOptions as opt}
						<option value={opt.value}>{opt.label}</option>
					{/each}
				</select>
			</label>
		</div>

		<!-- VL toggle -->
		<div class="flex items-center gap-3 mb-4 p-3 rounded-lg bg-zinc-900/30 border border-zinc-800/30">
			<label class="relative inline-flex items-center cursor-pointer">
				<input
					type="checkbox"
					checked={profile.has_versement_liberatoire ?? true}
					onchange={async (e) => {
						const val = (e.target as HTMLInputElement).checked;
						profile.has_versement_liberatoire = val;
						await immediateSave('has_versement_liberatoire', val);
					}}
					class="sr-only peer"
				/>
				<div class="w-9 h-5 bg-zinc-700 peer-focus:outline-none peer-focus:ring-1 peer-focus:ring-amber-500/40 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-600"></div>
			</label>
			<div>
				<span class="text-[11px] text-zinc-300 font-medium">Versement libératoire (IR)</span>
				<p class="text-[10px] text-zinc-500">
					{#if profile.has_versement_liberatoire !== false}
						Activé — l'impôt sur le revenu est prélevé à la source (+ ~2.2% sur le CA)
					{:else}
						Désactivé — l'IR est calculé séparément via le barème progressif
					{/if}
				</p>
			</div>
		</div>

		<!-- Rate schedule preview -->
		{#if rateSchedule.length > 0}
			<div class="mt-4">
				<h3 class="text-[11px] text-zinc-400 font-semibold mb-2">Projection des taux de cotisation</h3>
				<div class="flex flex-wrap gap-2">
					{#each rateSchedule as entry}
						<div class="bg-zinc-800/40 border border-zinc-700/30 rounded-lg px-3 py-1.5 text-center min-w-[60px]">
							<span class="block text-[9px] text-zinc-500">{entry.from_year}</span>
							<span class="block text-[11px] font-mono text-amber-300 font-semibold">{formatPercent(entry.rate)}</span>
						</div>
					{/each}
				</div>
				<p class="text-[9px] text-zinc-600 mt-2">Projections basées sur les tendances législatives. Les taux réels peuvent varier.</p>
			</div>
		{/if}
	</Card>
</div>