<script lang="ts">
	/**
	 * Savings page — 7 investment vehicle configurations with stats row.
	 *
	 * Displays all 7 vehicles (Livret A → PER) with balance and contribution
	 * inputs. Auto-saves each vehicle independently on change (debounce 800ms).
	 * Stats row shows total existing savings, monthly contributions, and annual.
	 */
	import { api } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import VehicleCard from '$lib/components/VehicleCard.svelte';
	import type { PageData } from './$types';

	export let data: PageData;

	let allocations = data.allocations ?? [];

	// ── Stats ─────────────────────────────────────────────────────────────
	let totalExisting = data.total_existing ? parseFloat(data.total_existing) : 0;
	let totalMonthly = data.total_monthly ? parseFloat(data.total_monthly) : 0;
	$: totalAnnual = totalMonthly * 12;

	// ── Auto-save ─────────────────────────────────────────────────────────
	const DEBOUNCE_MS = 800;
	let saveIndicator: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
	let timers: Record<string, ReturnType<typeof setTimeout>> = {};

	async function saveVehicle(
		vehicle_key: string,
		existing_balance: number,
		monthly_contribution: number
	) {
		saveIndicator = 'saving';
		try {
			const updated = await api.put(`/investments/${vehicle_key}`, {
				existing_balance,
				monthly_contribution,
			});

			// Update local allocation with server response
			const idx = allocations.findIndex(
				(a: any) => a.vehicle_key === vehicle_key
			);
			if (idx !== -1) {
				allocations[idx] = updated;
			}

			// Recompute totals from allocations
			recomputeTotals();

			saveIndicator = 'saved';
			setTimeout(() => {
				saveIndicator = 'idle';
			}, 1500);
		} catch (err) {
			console.error('[savings] Save failed:', err);
			saveIndicator = 'error';
		}
	}

	function handleVehicleChange(e: CustomEvent<{
		vehicle_key: string;
		existing_balance: number;
		monthly_contribution: number;
	}>) {
		const { vehicle_key, existing_balance, monthly_contribution } = e.detail;
		clearTimeout(timers[vehicle_key]);
		saveIndicator = 'saving';
		timers[vehicle_key] = setTimeout(
			() => saveVehicle(vehicle_key, existing_balance, monthly_contribution),
			DEBOUNCE_MS
		);
	}

	function recomputeTotals() {
		totalExisting = allocations.reduce(
			(sum: number, a: any) => sum + parseFloat(a.existing_balance || '0'),
			0
		);
		totalMonthly = allocations.reduce(
			(sum: number, a: any) => sum + parseFloat(a.monthly_contribution || '0'),
			0
		);
	}

	// ── Formatting ────────────────────────────────────────────────────────
	function fmt(n: number): string {
		if (n == null || isNaN(n)) return '— €';
		return n.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + '€';
	}

	function fmtK(n: number): string {
		if (n == null || isNaN(n)) return '—';
		if (Math.abs(n) >= 1000) {
			return (
				(n / 1000).toLocaleString('fr-FR', {
					minimumFractionDigits: 1,
					maximumFractionDigits: 1,
				}) + ' k€'
			);
		}
		return n.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + '€';
	}

	$: indicatorText =
		saveIndicator === 'saved'
			? '✓ Enregistré'
			: saveIndicator === 'saving'
				? '↻ Enregistrement...'
				: saveIndicator === 'error'
					? '✗ Erreur'
					: '';

	// ── Stat cards — reactive so values update with totals ────────────────
	$: statCards = [
		{
			label: 'Épargne existante',
			value: fmtK(totalExisting),
			accent: 'purple',
		},
		{
			label: 'Versement mensuel',
			value: fmt(totalMonthly),
			accent: 'teal',
		},
		{
			label: 'Versement annuel',
			value: fmt(totalAnnual),
			accent: 'teal',
		},
	];
</script>

<svelte:head>
	<title>Épargne — Horizon</title>
</svelte:head>

<div class="space-y-5">
	<!-- Save indicator -->
	<div class="flex items-center justify-end gap-2 h-4">
		<span
			class="text-[10px] {saveIndicator === 'saved'
				? 'text-emerald-400'
				: saveIndicator === 'error'
					? 'text-rose-400'
					: 'text-zinc-500'}"
		>
			{indicatorText}
		</span>
	</div>

	<!-- Stats Row -->
	<div class="grid grid-cols-3 gap-3">
		{#each statCards as card}
			<div
				class="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-3 text-center"
			>
				<span
					class="text-lg font-bold font-mono text-{card.accent}-300 block"
					>{card.value}</span
				>
				<span class="text-[10px] text-zinc-400">{card.label}</span>
			</div>
		{/each}
	</div>

	<!-- Vehicle list -->
	<Card
		title="Épargne & allocation mensuelle"
		icon="◆"
		accent="purple"
		dataCocoDesc="Configuration des 7 véhicules d'épargne — Livret A, LDDS, assurance-vie, PEA, SCPI, PER"
	>
		<p class="text-[11px] text-zinc-400 mb-4">
			Où va votre épargne mensuelle ? Renseignez vos soldes actuels et
			vos versements mensuels pour chaque véhicule.
		</p>

		{#if allocations.length > 0}
			{#each allocations as alloc (alloc.vehicle_key)}
				<VehicleCard
					allocation={alloc}
					on:change={handleVehicleChange}
				/>
			{/each}
		{:else}
			<p class="text-[11px] text-zinc-500 text-center py-8">
				Chargement des véhicules...
			</p>
		{/if}
	</Card>
</div>