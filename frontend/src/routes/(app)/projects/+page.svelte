<script lang="ts">
	/**
	 * Projects page — Investments, Life Events, and Status Change simulation.
	 *
	 * Three sections in order:
	 * 1. Investment projects (emerald) — mini P&L per project
	 * 2. Life events (amber) — one-time expense spikes
	 * 3. Status change simulation (teal) — AE → EIRL etc. with full comparison table
	 */
	import { api } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import type { PageData } from './$types';

	export let data: PageData;

	$: investmentProjects = data.investments ?? [];
	$: eventProjects = data.events ?? [];
	let profile = data.profile ?? {};

	// ── Auto-save ─────────────────────────────────────────────────────────
	const DEBOUNCE_MS = 800;
	let saveIndicator: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
	let timers: Record<string, ReturnType<typeof setTimeout>> = {};

	async function saveProject(id: string, updates: Record<string, unknown>) {
		saveIndicator = 'saving';
		try {
			const updated = await api.put(`/projects/${id}`, updates);
			const invIdx = investmentProjects.findIndex((p: any) => p.id === id);
			if (invIdx !== -1) investmentProjects[invIdx] = updated;
			const evIdx = eventProjects.findIndex((p: any) => p.id === id);
			if (evIdx !== -1) eventProjects[evIdx] = updated;
			saveIndicator = 'saved';
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[projects] Save failed:', err);
			saveIndicator = 'error';
		}
	}

	function debouncedSave(id: string, updates: Record<string, unknown>) {
		clearTimeout(timers[id]);
		saveIndicator = 'saving';
		timers[id] = setTimeout(() => saveProject(id, updates), DEBOUNCE_MS);
	}

	async function saveProfile(field: string, value: unknown) {
		try {
			const updated = await api.put('/profile', { [field]: value });
			profile = updated;
		} catch (err) {
			console.error('[projects] Profile save failed:', err);
		}
	}

	function debouncedProfileSave(field: string, value: unknown) {
		const key = `profile_${field}`;
		clearTimeout(timers[key]);
		saveIndicator = 'saving';
		timers[key] = setTimeout(() => saveProfile(field, value), DEBOUNCE_MS);
	}

	async function addInvestment() {
		try {
			const created = await api.post('/projects/investment', {
				label: 'Nouveau projet', start_year: 2035,
				purchase_cost: 80000, annual_income: 8000,
				annual_expenses: 2500, tax_rate: 0.30,
			});
			investmentProjects = [...investmentProjects, created];
			saveIndicator = 'saved';
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[projects] Add investment failed:', err);
		}
	}

	async function addEvent() {
		try {
			const created = await api.post('/projects/event', {
				label: 'Événement', event_year: 2030, event_cost: 10000,
			});
			eventProjects = [...eventProjects, created];
			saveIndicator = 'saved';
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[projects] Add event failed:', err);
		}
	}

	async function deleteProject(id: string) {
		if (!confirm('Supprimer ce projet ?')) return;
		try {
			await api.delete(`/projects/${id}`);
			investmentProjects = investmentProjects.filter((p: any) => p.id !== id);
			eventProjects = eventProjects.filter((p: any) => p.id !== id);
		} catch (err) {
			console.error('[projects] Delete failed:', err);
		}
	}

	// ── Formatting (null-safe) ────────────────────────────────────────────
	function fmt(n: number): string {
		if (n == null || isNaN(n)) return '— €';
		return n.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + '€';
	}
	function fmtPct(n: number): string {
		if (n == null || isNaN(n) || n === 0) return '—';
		return (n * 100).toFixed(1).replace('.', ',') + '%';
	}

	$: indicatorText =
		saveIndicator === 'saved' ? '✓ Enregistré'
		: saveIndicator === 'saving' ? '↻ Enregistrement...'
		: saveIndicator === 'error' ? '✗ Erreur'
		: '';

	// ── Status change state ───────────────────────────────────────────────
	let statusEnabled = profile?.status_change_enabled === true;
	let statusYear = profile?.status_change_year || 2028;
	let statusTarget = profile?.status_change_target || 'eirl';
	let statusSavings = profile?.status_change_savings ? parseFloat(profile.status_change_savings) : 0;

	const TARGET_STATUSES = [
		{ value: 'eirl', label: 'EIRL / EI', note: 'Responsabilité limitée, frais de compta modérés' },
		{ value: 'eurl', label: 'EURL (IS)', note: 'Impôt sur les sociétés, dividendes possibles' },
		{ value: 'sasu', label: 'SASU (IS)', note: 'Régime salarié dirigeant, plus de protection sociale' },
	];

	// ── Professional charges estimator ────────────────────────────────────
	let showEstimator = true; // open by default for clarity
	let estInternet = 50;
	let estBureau = 200;
	let estVoiture = 250;
	let estRepas = 150;
	let estAutres = 0;

	$: monthlyGrossCA = profile?.monthly_gross_ca ? parseFloat(profile.monthly_gross_ca) : 0;
	$: annualGrossCA = monthlyGrossCA * 12;
	$: totalCharges = (estInternet + estBureau + estVoiture + estRepas + estAutres) * 12;

	// AE rates from profile or defaults
	$: aeActivityType = profile?.ae_activity_type || 'bnc_non_reglementee';
	$: abattementRate = aeActivityType === 'bic_vente' ? 0.71
		: aeActivityType === 'bic_services' ? 0.50
		: 0.34; // BNC default
	$: cotisationRate = aeActivityType === 'bic_vente' ? 0.148
		: aeActivityType === 'bic_services' ? 0.237
		: 0.262; // BNC default
	$: abattementAE = annualGrossCA * abattementRate;
	$: baseAE = Math.max(0, annualGrossCA - abattementAE);
	$: cotisationsAE = Math.round(baseAE * cotisationRate);
	// Target status: always compute the real diff, don't zero out when AE is better
	$: targetRate = 0.45; // ~45% TNS/charges dirigeant for all target statuses in MVP
	$: baseTarget = Math.max(0, annualGrossCA - totalCharges);
	$: cotisationsTarget = Math.round(baseTarget * targetRate);
	// economie: positive = target pays MORE in cotisations = AE advantage (AE keeps this much more)
	$: economie = cotisationsTarget - cotisationsAE;
	$: netAE = annualGrossCA - cotisationsAE;
	$: netTarget = annualGrossCA - cotisationsTarget;
	// netDiff: positive = AE keeps more
	$: netDiff = netAE - netTarget;

	$: caLabel = aeActivityType === 'bic_vente' ? 'BIC vente' : aeActivityType === 'bic_services' ? 'BIC services' : 'BNC';

	function applyEstimate() {
		if (economie > 0) {
			statusSavings = economie;
			debouncedProfileSave('status_change_savings', economie);
		}
	}
</script>

<svelte:head>
	<title>Projets — Horizon</title>
</svelte:head>

<div class="space-y-5">
	<!-- Save indicator -->
	<div class="flex items-center justify-end gap-2 h-4">
		<span class="text-[10px] {saveIndicator === 'saved' ? 'text-emerald-400' : saveIndicator === 'error' ? 'text-rose-400' : 'text-zinc-500'}">{indicatorText}</span>
	</div>

	<!-- ━━━━━━━━━━━ SECTION 1: Investments ━━━━━━━━━━━ -->
	<Card title="Investissements 🏡" icon="🏡" accent="emerald" dataCocoDesc="Projets d'investissement — immobilier locatif, gîte, avec mini P&L par projet">
		<p class="text-[11px] text-zinc-400 mb-4">Immobilier locatif, gîte — chaque projet a son mini bilan : revenus, charges, fiscalité.</p>
		{#each investmentProjects as proj (proj.id)}
			{@const p = proj}
			{@const pnl = p.pnl}
			<div class="border border-zinc-800/30 rounded-lg p-3 mb-3" data-coco-desc="Projet {p.label} — achat {p.purchase_cost}€, revenus {p.annual_income}€/an">
				<div class="flex items-end gap-3 mb-3">
					<label class="flex flex-col gap-1 flex-1">
						<span class="text-[10px] text-zinc-500 font-medium">Nom</span>
						<input type="text" value={p.label}
							oninput={(e) => { const val = (e.target as HTMLInputElement).value; p.label = val; debouncedSave(p.id, { label: val }); }}
							class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-emerald-500/60 w-full" />
					</label>
					<label class="flex flex-col gap-1 w-20">
						<span class="text-[10px] text-zinc-500 font-medium">Année</span>
						<input type="number" min="2024" max="2080" value={p.start_year || ''}
							oninput={(e) => { const val = parseInt((e.target as HTMLInputElement).value); if (!isNaN(val)) { p.start_year = val; debouncedSave(p.id, { start_year: val }); } }}
							class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-emerald-500/60 w-full" />
					</label>
					<button onclick={() => deleteProject(p.id)} class="text-zinc-500 hover:text-rose-400 mb-1.5 text-sm" title="Supprimer">✕</button>
				</div>
				<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
					<label class="flex flex-col gap-1">
						<span class="text-[10px] text-zinc-500 font-medium">Coût d'achat</span>
						<input type="number" min="0" step="1000" value={p.purchase_cost ? parseFloat(p.purchase_cost) : ''} placeholder="0"
							oninput={(e) => { const val = parseFloat((e.target as HTMLInputElement).value); if (!isNaN(val) && val >= 0) { p.purchase_cost = val.toString(); debouncedSave(p.id, { purchase_cost: val }); } }}
							class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-emerald-500/60 w-full" />
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-[10px] text-zinc-500 font-medium">Revenus locatifs/an</span>
						<input type="number" min="0" step="500" value={p.annual_income ? parseFloat(p.annual_income) : ''} placeholder="0"
							oninput={(e) => { const val = parseFloat((e.target as HTMLInputElement).value); if (!isNaN(val) && val >= 0) { p.annual_income = val.toString(); debouncedSave(p.id, { annual_income: val }); } }}
							class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-emerald-500/60 w-full" />
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-[10px] text-zinc-500 font-medium">Charges annuelles</span>
						<span class="text-[8px] text-zinc-600 leading-tight">Ménage, entretien, assurance, travaux</span>
						<input type="number" min="0" step="100" value={p.annual_expenses ? parseFloat(p.annual_expenses) : ''} placeholder="0"
							oninput={(e) => { const val = parseFloat((e.target as HTMLInputElement).value); if (!isNaN(val) && val >= 0) { p.annual_expenses = val.toString(); debouncedSave(p.id, { annual_expenses: val }); } }}
							class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-emerald-500/60 w-full" />
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-[10px] text-zinc-500 font-medium">Taux d'imposition</span>
						<span class="text-[8px] text-zinc-600 leading-tight">30% micro-foncier, variable en réel</span>
						<input type="number" min="0" max="100" step="1" value={p.tax_rate ? Math.round(parseFloat(p.tax_rate) * 100) : ''} placeholder="30"
							oninput={(e) => { const val = parseFloat((e.target as HTMLInputElement).value) / 100; if (!isNaN(val) && val >= 0 && val <= 1) { p.tax_rate = val.toString(); debouncedSave(p.id, { tax_rate: val }); } }}
							class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-emerald-500/60 w-full" />
					</label>
				</div>
				{#if pnl}
					<div class="mt-2 p-2 rounded bg-zinc-800/30 flex flex-wrap gap-4 text-xs">
						<span class="text-zinc-400">Brut/an: <strong class="text-zinc-200">{fmt(parseFloat(pnl.gross_annual))}</strong></span>
						<span class="text-zinc-400">Net: <strong class={parseFloat(pnl.net_annual) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>{fmt(parseFloat(pnl.net_annual))}</strong>/an</span>
						<span class="text-zinc-400">Rendement: <strong class="text-teal-400">{pnl.yield_pct ? fmtPct(parseFloat(pnl.yield_pct)) : '—'}</strong></span>
					</div>
					{#if parseFloat(pnl.net_annual) < 0}
						<p class="text-[10px] text-rose-400 mt-1">Ce projet coûte plus qu'il ne rapporte</p>
					{/if}
				{/if}
			</div>
		{/each}
		<button onclick={addInvestment} class="w-full border border-dashed border-emerald-700/40 rounded-lg py-2.5 text-xs text-emerald-400 hover:text-emerald-300 hover:border-emerald-500/60 transition-colors">+ Ajouter un investissement</button>
	</Card>

	<!-- ━━━━━━━━━━━ SECTION 2: Life Events ━━━━━━━━━━━ -->
	<Card title="Événements de vie ponctuels 🎉" icon="🎉" accent="amber" dataCocoDesc="Événements ponctuels — mariage, voyage, rénovation — dépenses one-shot">
		<p class="text-[11px] text-zinc-400 mb-4">Mariage, grand voyage, grosse rénovation — dépenses one-shot qui impactent votre trésorerie.</p>
		{#each eventProjects as proj (proj.id)}
			{@const p = proj}
			<div class="flex items-end gap-3 mb-2" data-coco-desc="Événement {p.label} en {p.event_year} — {p.event_cost}€">
				<label class="flex flex-col gap-1 flex-1">
					<span class="text-[10px] text-zinc-500 font-medium">Description</span>
					<input type="text" value={p.label}
						oninput={(e) => { const val = (e.target as HTMLInputElement).value; p.label = val; debouncedSave(p.id, { label: val }); }}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-amber-500/60 w-full" />
				</label>
				<label class="flex flex-col gap-1 w-24">
					<span class="text-[10px] text-zinc-500 font-medium">Année</span>
					<input type="number" min="2024" max="2080" value={p.event_year || ''}
						oninput={(e) => { const val = parseInt((e.target as HTMLInputElement).value); if (!isNaN(val)) { p.event_year = val; debouncedSave(p.id, { event_year: val }); } }}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-amber-500/60 w-full" />
				</label>
				<label class="flex flex-col gap-1 w-28">
					<span class="text-[10px] text-zinc-500 font-medium">Coût</span>
					<input type="number" min="0" step="500" value={p.event_cost ? parseFloat(p.event_cost) : ''} placeholder="0"
						oninput={(e) => { const val = parseFloat((e.target as HTMLInputElement).value); if (!isNaN(val) && val >= 0) { p.event_cost = val.toString(); debouncedSave(p.id, { event_cost: val }); } }}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-amber-500/60 w-full" />
				</label>
				<button onclick={() => deleteProject(p.id)} class="text-zinc-500 hover:text-rose-400 mb-2 text-sm" title="Supprimer">✕</button>
			</div>
		{/each}
		<button onclick={addEvent} class="w-full border border-dashed border-amber-700/40 rounded-lg py-2.5 text-xs text-amber-400 hover:text-amber-300 hover:border-amber-500/60 transition-colors">+ Ajouter un événement</button>
	</Card>

	<!-- ━━━━━━━━━━━ SECTION 3: Status Change (redesigned) ━━━━━━━━━━━ -->
	<Card title="Changement de statut juridique 🔄" icon="🔄" accent="teal" dataCocoDesc="Simulation de changement de statut juridique — comparez AE vs EIRL/EURL/SASU avec un tableau détaillé">
		<!-- Explainer -->
		<div class="text-[11px] text-zinc-400 mb-4 p-3 rounded-lg bg-zinc-900/30 border border-zinc-800/40 leading-relaxed">
			<strong class="text-zinc-200">Comment ça marche :</strong> En micro-entreprise (AE), vous ne pouvez pas déduire vos vraies charges professionnelles — l'État applique un <strong>abattement forfaitaire</strong> ({caLabel} : {(abattementRate * 100).toFixed(0)}% du CA).
			Si vos charges réelles (internet, bureau, voiture, repas…) dépassent cet abattement, passer en EIRL/EURL/SASU permet de <strong>déduire vos vraies charges</strong> → vous payez moins de cotisations.
		</div>

		<!-- Toggle -->
		<label class="flex items-center gap-3 mb-4 cursor-pointer">
			<input type="checkbox" checked={statusEnabled}
				onchange={(e) => { statusEnabled = (e.target as HTMLInputElement).checked; debouncedProfileSave('status_change_enabled', statusEnabled); }}
				class="w-4 h-4 rounded border-zinc-600 bg-zinc-900 text-teal-500 focus:ring-teal-500/30" />
			<span class="text-xs text-zinc-300 font-medium">Simuler un changement de statut</span>
		</label>

		{#if statusEnabled}
			<!-- Step 1: Target settings -->
			<div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
				<label class="flex flex-col gap-1">
					<span class="text-[10px] text-zinc-500 font-medium">1. Année du changement</span>
					<input type="number" min="2024" max="2080" value={statusYear}
						oninput={(e) => { const val = parseInt((e.target as HTMLInputElement).value); if (!isNaN(val)) { statusYear = val; debouncedProfileSave('status_change_year', val); } }}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full" />
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-[10px] text-zinc-500 font-medium">2. Nouveau statut</span>
					<select value={statusTarget}
						onchange={(e) => { statusTarget = (e.target as HTMLSelectElement).value; debouncedProfileSave('status_change_target', statusTarget); }}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full">
						{#each TARGET_STATUSES as opt}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>
					<span class="text-[9px] text-zinc-600">{TARGET_STATUSES.find(s => s.value === statusTarget)?.note || ''}</span>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-[10px] text-zinc-500 font-medium">3. Économie annuelle estimée</span>
					<div class="flex items-center gap-2">
						<span class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm font-mono w-full {statusSavings > 0 ? 'text-teal-300' : 'text-zinc-500'}">
							{statusSavings > 0 ? fmt(statusSavings) : '—'}
						</span>
						{#if economie > 0 && economie !== statusSavings}
							<button class="text-[10px] bg-teal-600/60 hover:bg-teal-600 text-white rounded px-2 py-1 whitespace-nowrap"
								onclick={applyEstimate}>Appliquer {fmt(economie)}</button>
						{/if}
					</div>
					<span class="text-[8px] text-zinc-600 leading-tight">Remplissez le simulateur ci-dessous puis cliquez "Appliquer"</span>
				</label>
			</div>

			<!-- Step 2: Charges estimator -->
			<button onclick={() => (showEstimator = !showEstimator)} class="text-[11px] text-teal-400 hover:text-teal-300 transition-colors mb-3">
				{showEstimator ? '▼ Masquer le simulateur de charges' : '▶ Estimez vos charges professionnelles réelles'}
			</button>

			{#if showEstimator}
				<div class="p-4 rounded-lg bg-zinc-900/40 border border-zinc-800/40 mb-5">
					<p class="text-[10px] text-zinc-500 mb-3">Entrez vos charges pro mensuelles <strong>réelles</strong>. L'abattement AE est calculé automatiquement depuis votre CA ({fmt(monthlyGrossCA)}/mois).</p>
					<div class="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
						{#each [
							{ label: 'Internet', bind: estInternet },
							{ label: 'Bureau', bind: estBureau },
							{ label: 'Voiture pro', bind: estVoiture },
							{ label: 'Repas midi', bind: estRepas },
							{ label: 'Autres', bind: estAutres }
						] as cat}
							<label class="flex flex-col gap-1">
								<span class="text-[9px] text-zinc-500">{cat.label}</span>
								<div class="relative">
									<input type="number" min="0" step="10" bind:value={cat.bind}
										class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg pl-2 pr-8 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full" />
									<span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-zinc-600">€/m</span>
								</div>
							</label>
						{/each}
					</div>

					<!-- Calculation breakdown -->
					<div class="text-[10px] space-y-1.5 p-3 rounded bg-zinc-800/30 mb-3">
						<div class="flex justify-between"><span class="text-zinc-400">Charges pro réelles</span><span class="font-mono text-zinc-200">{fmt(totalCharges)}/an</span></div>
						<div class="flex justify-between"><span class="text-zinc-400">Abattement AE ({caLabel} {(abattementRate * 100).toFixed(0)}% × {fmt(annualGrossCA)})</span><span class="font-mono text-zinc-200">{fmt(Math.round(abattementAE))}/an</span></div>
						<div class="flex justify-between border-t border-zinc-700/50 pt-1.5">
							<span class="text-zinc-400">Base cotisations AE</span><span class="font-mono text-zinc-200">{fmt(baseAE)}/an</span>
						</div>
						<div class="flex justify-between"><span class="text-zinc-400">Cotisations AE ({(cotisationRate * 100).toFixed(1)}%)</span><span class="font-mono text-rose-400">−{fmt(cotisationsAE)}/an</span></div>
						<div class="flex justify-between border-t border-zinc-700/50 pt-1.5">
							<span class="text-zinc-400">Base cotisations {statusTarget.toUpperCase()}</span><span class="font-mono text-zinc-200">{fmt(baseTarget)}/an</span>
						</div>
						<div class="flex justify-between"><span class="text-zinc-400">Cotisations {statusTarget.toUpperCase()} (~45% TNS)</span><span class="font-mono text-rose-400">−{fmt(cotisationsTarget)}/an</span></div>
					</div>

					<!-- Comparison table -->
					<div class="overflow-x-auto">
						<table class="w-full text-[10px]">
							<thead>
								<tr class="border-b border-zinc-700/50 text-zinc-500">
									<th class="py-1.5 text-left font-medium">Poste</th>
									<th class="py-1.5 text-right font-medium">AE (actuel)</th>
									<th class="py-1.5 text-right font-medium">{statusTarget.toUpperCase()} (cible)</th>
									<th class="py-1.5 text-right font-medium">Différence</th>
								</tr>
							</thead>
							<tbody class="text-zinc-300">
								<tr class="border-b border-zinc-800/30">
									<td class="py-1.5">CA annuel brut</td>
									<td class="py-1.5 text-right font-mono">{fmt(annualGrossCA)}</td>
									<td class="py-1.5 text-right font-mono">{fmt(annualGrossCA)}</td>
									<td class="py-1.5 text-right font-mono text-zinc-500">—</td>
								</tr>
								<tr class="border-b border-zinc-800/30">
									<td class="py-1.5">Charges déductibles</td>
									<td class="py-1.5 text-right font-mono">{fmt(Math.round(abattementAE))}</td>
									<td class="py-1.5 text-right font-mono">{fmt(totalCharges)}</td>
									<td class="py-1.5 text-right font-mono {totalCharges > abattementAE ? 'text-teal-400' : 'text-amber-400'}">{totalCharges > abattementAE ? '+' : ''}{fmt(Math.round(totalCharges - abattementAE))}</td>
								</tr>
								<tr class="border-b border-zinc-800/30">
									<td class="py-1.5">Base cotisations</td>
									<td class="py-1.5 text-right font-mono">{fmt(baseAE)}</td>
									<td class="py-1.5 text-right font-mono">{fmt(baseTarget)}</td>
									<td class="py-1.5 text-right font-mono {baseTarget > baseAE ? 'text-amber-400' : baseTarget < baseAE ? 'text-emerald-400' : 'text-zinc-500'}">
										{baseTarget > baseAE ? '+' : baseTarget < baseAE ? '−' : ''}{fmt(Math.abs(Math.round(baseTarget - baseAE)))}
									</td>
								</tr>
								<tr class="border-b border-zinc-800/30">
									<td class="py-1.5">Cotisations sociales</td>
									<td class="py-1.5 text-right font-mono text-rose-400">−{fmt(cotisationsAE)}</td>
									<td class="py-1.5 text-right font-mono text-rose-400">−{fmt(cotisationsTarget)}</td>
									<td class="py-1.5 text-right font-mono {economie > 0 ? 'text-emerald-400' : economie < 0 ? 'text-rose-400' : 'text-zinc-500'}">
										{economie > 0 ? '+' : ''}{fmt(Math.abs(economie))}
									</td>
								</tr>
								<tr class="border-t border-zinc-600/30 font-semibold">
									<td class="py-2">Net après cotisations</td>
									<td class="py-2 text-right font-mono text-zinc-200">{fmt(netAE)}</td>
									<td class="py-2 text-right font-mono text-zinc-200">{fmt(netTarget)}</td>
									<td class="py-2 text-right font-mono {netDiff > 0 ? 'text-emerald-400' : netDiff < 0 ? 'text-rose-400' : 'text-zinc-500'}">
										{netDiff > 0 ? '+' : ''}{fmt(Math.abs(netDiff))}/an
									</td>
								</tr>
							</tbody>
						</table>
					</div>

					<!-- Conclusion based on netDiff -->
					{#if netDiff > 0}
						<div class="mt-3 p-2 rounded bg-emerald-950/20 border border-emerald-900/20">
							<p class="text-[10px] text-emerald-300">✓ L'AE reste plus avantageux — vous gardez <strong>~{fmt(netDiff)}/an</strong> de plus qu'en {statusTarget.toUpperCase()}.</p>
						</div>
					{:else if netDiff < 0}
						<div class="mt-3 p-2 rounded bg-teal-950/20 border border-teal-900/20">
							<p class="text-[10px] text-teal-300">✓ Le passage en {statusTarget.toUpperCase()} serait avantageux — vous gagneriez <strong>~{fmt(-netDiff)}/an</strong>. Cliquez "Appliquer" ci-dessus pour l'enregistrer dans votre projection Horizon.</p>
						</div>
					{:else}
						<div class="mt-3 p-2 rounded bg-zinc-800/30 border border-zinc-700/40">
							<p class="text-[10px] text-zinc-400">Les deux statuts sont équivalents pour votre situation actuelle.</p>
						</div>
					{/if}
				</div>
			{/if}
		{/if}
	</Card>
</div>