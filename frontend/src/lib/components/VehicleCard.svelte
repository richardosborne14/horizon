<script lang="ts">
	/**
	 * VehicleCard — single investment vehicle row with balance and contribution inputs.
	 *
	 * Displays vehicle specs (rate, tax, ceiling, risk) and two number inputs.
	 * Auto-saves on input change (debounced via parent).
	 */
	import { createEventDispatcher } from 'svelte';

	export let allocation: {
		id: string;
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
		};
		warning: string | null;
	};

	const dispatch = createEventDispatcher<{
		change: {
			vehicle_key: string;
			existing_balance: number;
			monthly_contribution: number;
		};
	}>();

	let localBalance = allocation.existing_balance
		? parseFloat(allocation.existing_balance)
		: 0;
	let localContribution = allocation.monthly_contribution
		? parseFloat(allocation.monthly_contribution)
		: 0;

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
		allocation.spec.tax_deductible
			? 'déductible IR'
			: null,
	]
		.filter(Boolean)
		.join(' • ');

	// ── Emit changes ─────────────────────────────────────────────────────
	function handleBalanceInput(e: Event) {
		const val = parseFloat((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) {
			localBalance = val;
			dispatch('change', {
				vehicle_key: allocation.vehicle_key,
				existing_balance: val,
				monthly_contribution: localContribution,
			});
		}
	}

	function handleContributionInput(e: Event) {
		const val = parseFloat((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) {
			localContribution = val;
			dispatch('change', {
				vehicle_key: allocation.vehicle_key,
				existing_balance: localBalance,
				monthly_contribution: val,
			});
		}
	}
</script>

<div
	class="border border-zinc-800/30 rounded-lg p-3 mb-3"
	data-coco-desc="Véhicule d'épargne {allocation.spec.label} — taux {allocation.spec.rate}, risque {allocation.spec.risk}"
>
	<!-- Header row -->
	<div class="flex items-center gap-2 mb-2">
		<div
			class="w-2.5 h-2.5 rounded-full flex-shrink-0"
			style="background-color: {allocation.spec.color}"
		></div>
		<span class="text-xs font-semibold text-zinc-200"
			>{allocation.spec.label}</span
		>
		<span class="text-[10px] text-zinc-500 font-mono ml-auto hidden sm:inline"
			>{specLine}</span
		>
	</div>

	<!-- Mobile spec summary -->
	<div class="sm:hidden text-[10px] text-zinc-500 font-mono mb-2">
		{specLine}
	</div>

	<!-- Inputs row -->
	<div class="flex gap-3">
		<label class="flex flex-col gap-1 flex-1">
			<span class="text-[10px] text-zinc-500 font-medium"
				>Solde actuel</span
			>
			<input
				type="number"
				min="0"
				step="100"
				value={localBalance || ''}
				placeholder="0"
				oninput={handleBalanceInput}
				class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-purple-500/60 w-full"
			/>
		</label>
		<label class="flex flex-col gap-1 flex-1">
			<span class="text-[10px] text-zinc-500 font-medium"
				>Versement mensuel</span
			>
			<input
				type="number"
				min="0"
				step="10"
				value={localContribution || ''}
				placeholder="0"
				oninput={handleContributionInput}
				class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-purple-500/60 w-full"
			/>
		</label>
	</div>

	<!-- Ceiling warning -->
	{#if allocation.warning}
		<p class="text-[10px] text-amber-400 mt-1.5">
			⚠️ {allocation.warning}
		</p>
	{/if}
</div>