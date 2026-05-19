<script lang="ts">
	/**
	 * VehicleCard — single investment vehicle row with balance and contribution inputs.
	 *
	 * TASK-8.9: Added ℹ️ rules panel toggle showing rate, tax, ceiling, liquidity,
	 * lock_up, best_for, watch_out from VEHICLE_RULES. Informational vehicles
	 * (LEP, PEL, CTO, PEE) are shown greyed with an "Ajouter" button when
	 * they have no allocation yet.
	 */
	import { createEventDispatcher } from 'svelte';
	import { api } from '$lib/api';

	export let allocation: {
		id?: string;
		vehicle_key: string;
		existing_balance: string;
		monthly_contribution: string;
		spec: {
			key: string;
			label: string;
			description: string;
			rate: string;
			tax_free: boolean;
			tax_rate: string;
			ceiling: string | null;
			risk: string;
			color: string;
			liquidity: string;
			tax_deductible: boolean;
			informational: boolean;
			lock_up_years: number | null;
		};
		warning: string | null;
	} = {
		vehicle_key: '',
		existing_balance: '0',
		monthly_contribution: '0',
		spec: {
			key: '',
			label: '',
			description: '',
			rate: '0',
			tax_free: false,
			tax_rate: '0',
			ceiling: null,
			risk: '',
			color: '#666',
			liquidity: '',
			tax_deductible: false,
			informational: false,
			lock_up_years: null,
		},
		warning: null,
	};

	const dispatch = createEventDispatcher<{
		change: {
			vehicle_key: string;
			existing_balance: number;
			monthly_contribution: number;
		};
		activate: {
			vehicle_key: string;
		};
	}>();

	// ── Local state ──────────────────────────────────────────────────────
	let showRules = false;
	let rules: Record<string, any> | null = null;
	let rulesLoading = false;

	let localBalance = allocation.existing_balance
		? parseFloat(allocation.existing_balance)
		: 0;
	let localContribution = allocation.monthly_contribution
		? parseFloat(allocation.monthly_contribution)
		: 0;

	const hasAllocation = !allocation.id?.startsWith('virtual-') &&
		(localBalance > 0 || localContribution > 0 ||
			(allocation.id && !allocation.spec.informational));
	const isInformational = allocation.spec.informational;
	const showAsNew = isInformational && !hasAllocation;

	// ── Formatting ────────────────────────────────────────────────────────
	function fmtPct(rate: string): string {
		const r = parseFloat(rate) * 100;
		return r.toFixed(1).replace('.', ',') + '%';
	}

	function fmtCeiling(ceiling: string): string {
		const c = parseFloat(ceiling);
		if (c >= 1000) {
			return (c / 1000)
				.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) +
				' k€';
		}
		return c.toLocaleString('fr-FR') + '€';
	}

	$: specLine = [
		fmtPct(allocation.spec.rate) + '/an',
		allocation.spec.tax_free
			? "net d'impôt"
			: fmtPct(allocation.spec.tax_rate) + ' PFU',
		allocation.spec.ceiling
			? 'plafond ' + fmtCeiling(allocation.spec.ceiling)
			: null,
		allocation.spec.lock_up_years
			? 'bloqué ' + allocation.spec.lock_up_years + ' ans'
			: null,
		allocation.spec.tax_deductible
			? 'déductible IR'
			: null,
	]
		.filter(Boolean)
		.join(' • ');

	// ── Load rules on demand ─────────────────────────────────────────────
	async function toggleRules() {
		showRules = !showRules;
		if (showRules && !rules) {
			rulesLoading = true;
			try {
				const resp = await api.get('/investments/catalog');
				const vehicles = (resp as any).vehicles || {};
				rules = vehicles[allocation.vehicle_key] || null;
			} catch (err) {
				console.error('[VehicleCard] Rules fetch failed:', err);
				rules = null;
			}
			rulesLoading = false;
		}
	}

	// ── Activate informational vehicle ──────────────────────────────────
	function activateVehicle() {
		localBalance = 0;
		localContribution = 0;
		dispatch('activate', { vehicle_key: allocation.vehicle_key });
	}

	// ── Emit changes ─────────────────────────────────────────────────────
	function handleBalanceInput(e: Event) {
		const val = parseFloat((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) {
			localBalance = val;
			dispatch('change', {
				vehicle_key: allocation.vehicle_key,
				existing_balance: localBalance,
				monthly_contribution: localContribution,
			});
		}
	}

	function handleContribInput(e: Event) {
		const val = parseFloat((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) {
			localContribution = val;
			dispatch('change', {
				vehicle_key: allocation.vehicle_key,
				existing_balance: localBalance,
				monthly_contribution: localContribution,
			});
		}
	}
</script>

<div class="border-b border-zinc-800/30 last:border-b-0 {showAsNew ? 'opacity-60' : ''}">
	<!-- Main row -->
	<div class="flex items-center gap-3 py-3 px-1">
		<!-- Color dot -->
		<span
			class="w-3 h-3 rounded-full flex-shrink-0"
			style="background-color: {allocation.spec.color}"
		></span>

		<!-- Label + spec line -->
		<div class="flex-1 min-w-0">
			<div class="flex items-center gap-1.5">
				<span class="text-xs font-medium text-zinc-200">
					{allocation.spec.label}
				</span>
				<button
					class="text-zinc-600 hover:text-zinc-300 transition-colors"
					onclick={toggleRules}
					title="Règles fiscales"
					data-coco-desc="Afficher les règles fiscales et conditions du véhicule {allocation.spec.label}"
				>
					<span class="text-[11px] {showRules ? 'text-sky-400' : ''}">ℹ️</span>
				</button>
			</div>
			<p class="text-[10px] text-zinc-500 mt-0.5">{specLine}</p>
			{#if allocation.warning}
				<p class="text-[9px] text-amber-400 mt-0.5">{allocation.warning}</p>
			{/if}
		</div>

		<!-- Inputs or Activate button -->
		{#if showAsNew}
			<button
				class="text-[10px] text-zinc-400 hover:text-white border border-zinc-700/40 hover:border-zinc-500/60 rounded px-2 py-1 transition-colors"
				onclick={activateVehicle}
				data-coco-desc="Ajouter {allocation.spec.label} à votre allocation"
			>
				+ Ajouter
			</button>
		{:else}
			<div class="flex items-center gap-2">
				<label class="flex flex-col items-end gap-0.5">
					<span class="text-[9px] text-zinc-600">Solde</span>
					<input
						type="number"
						min="0"
						step="100"
						value={localBalance || ''}
						oninput={handleBalanceInput}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1 text-xs text-zinc-200 text-right w-24 focus:outline-none focus:border-fuchsia-500/60 focus:ring-1 focus:ring-fuchsia-500/20"
						placeholder="0€"
						data-coco-desc="Solde actuel du {allocation.spec.label}"
					/>
				</label>
				<label class="flex flex-col items-end gap-0.5">
					<span class="text-[9px] text-zinc-600">/mois</span>
					<input
						type="number"
						min="0"
						step="50"
						value={localContribution || ''}
						oninput={handleContribInput}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1 text-xs text-zinc-200 text-right w-20 focus:outline-none focus:border-fuchsia-500/60 focus:ring-1 focus:ring-fuchsia-500/20"
						placeholder="0€"
						data-coco-desc="Versement mensuel dans le {allocation.spec.label}"
					/>
				</label>
			</div>
		{/if}
	</div>

	<!-- Rules panel (TASK-8.9.B) -->
	{#if showRules}
		<div class="pb-3 px-1 pl-7">
			{#if rulesLoading}
				<p class="text-[10px] text-zinc-500 italic">Chargement...</p>
			{:else if rules}
				<div class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg p-3 space-y-2" data-coco-desc={`Règles fiscales ${allocation.spec.label}`}>
					<div class="grid grid-cols-2 gap-2 text-[10px]">
						{#if rules.current_rate}
							<div>
								<span class="text-zinc-500">Taux actuel</span><br/>
								<span class="text-zinc-200 font-mono">{rules.current_rate}</span>
							</div>
						{/if}
						{#if rules.ceiling}
							<div>
								<span class="text-zinc-500">Plafond</span><br/>
								<span class="text-zinc-200">{rules.ceiling}</span>
							</div>
						{/if}
						{#if rules.tax}
							<div>
								<span class="text-zinc-500">Fiscalité</span><br/>
								<span class="text-zinc-200">{rules.tax}</span>
							</div>
						{/if}
						{#if rules.liquidity}
							<div>
								<span class="text-zinc-500">Liquidité</span><br/>
								<span class="text-zinc-200">{rules.liquidity}</span>
							</div>
						{/if}
						{#if rules.lock_up}
							<div>
								<span class="text-zinc-500">Blocage</span><br/>
								<span class="text-zinc-200">{rules.lock_up}</span>
							</div>
						{/if}
						{#if rules.horizon}
							<div>
								<span class="text-zinc-500">Horizon</span><br/>
								<span class="text-zinc-200">{rules.horizon}</span>
							</div>
						{/if}
						{#if rules.penalty}
							<div>
								<span class="text-zinc-500">Pénalité</span><br/>
								<span class="text-zinc-200">{rules.penalty}</span>
							</div>
						{/if}
					</div>

					{#if rules.best_for}
						<div class="pt-1.5 border-t border-zinc-700/30">
							<span class="text-[9px] text-emerald-400 font-medium">💡 Idéal pour</span>
							<p class="text-[10px] text-zinc-300 mt-0.5">{rules.best_for}</p>
						</div>
					{/if}

					{#if rules.watch_out}
						<div class="pt-1.5">
							<span class="text-[9px] text-amber-400 font-medium">⚠️ Attention</span>
							<p class="text-[10px] text-zinc-300 mt-0.5">{rules.watch_out}</p>
						</div>
					{/if}

					{#if rules.open_conditions}
						<div class="pt-1.5 border-t border-zinc-700/30">
							<span class="text-[9px] text-zinc-500">Conditions d'ouverture</span>
							<p class="text-[10px] text-zinc-400 mt-0.5">{rules.open_conditions}</p>
						</div>
					{/if}
				</div>
			{:else}
				<p class="text-[10px] text-zinc-600 italic">Aucune règle disponible.</p>
			{/if}
		</div>
	{/if}
</div>