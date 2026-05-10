<script lang="ts">
	/**
	 * Runway page — the payoff view. 30-year projection engine output rendered as:
	 * scale selector, goal input, hero stats, wealth chart, income chart,
	 * milestones timeline, projection table, insight cards, and disclaimer.
	 */
	import { onMount } from 'svelte';
	import { projectionStore, projectionLoading } from '$lib/stores/projection';
	import AreaChart from '$lib/components/runway/AreaChart.svelte';
	import InsightCards from '$lib/components/runway/InsightCards.svelte';
	import ReadinessGauge from '$lib/components/runway/ReadinessGauge.svelte';
	import ScenarioPanel from '$lib/components/runway/ScenarioPanel.svelte';
	import { fmt, fmtK, fmtPct } from '$lib/utils/format';
	import type { PageData } from './$types';

	export let data: PageData;

	// Local reactive state
	$: profile = data.profile;
	$: projection = $projectionStore || data.projection;
	$: loading = $projectionLoading;
	$: hasBirthdate = profile?.birth_date != null;
	$: serverError = data.error;
	$: showNoBirthdate = !hasBirthdate || serverError === 'no_birthdate' || serverError === 'no_profile';
	$: showApiError = serverError && serverError !== 'no_birthdate' && serverError !== 'no_profile';
	$: pensionEstimate = (data as any).pensionEstimate ?? null;
	$: netWorth = (data as any).netWorth ?? null;

	// Initialize store and Sprint 6 data from server
	let _s6Loaded = false;

	onMount(() => {
		if (data.projection) {
			projectionStore.set(data.projection);
		}
		_s6Loaded = true;
		loadAlerts();
		loadSensitivity();
	});

	// ── Scale selector ────────────────────────────────────────────────
	const SCALES = [
		{ key: 'optimistic', label: '☀️ Optimiste' },
		{ key: 'moderate', label: '⛅ Modéré' },
		{ key: 'pessimistic', label: '🌧️ Pessimiste' }
	];

	$: currentScale = projection?.scale || 'moderate';

	async function changeScale(newScale: string) {
		projectionLoading.set(true);
		try {
			const res = await fetch(`/api/projection?scale=${newScale}`);
			if (!res.ok) throw new Error('Scale fetch failed');
			const newData = await res.json();
			projectionStore.set(newData);
			await fetch('/api/profile', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ world_scale: newScale })
			});
		} catch (e) {
			console.error('Scale change failed:', e);
		} finally {
			projectionLoading.set(false);
		}
	}

	// ── Goal input ─────────────────────────────────────────────────────
	let goalValue = '';
	$: if (profile?.monthly_revenue_goal && !goalValue) {
		goalValue = String(profile.monthly_revenue_goal);
	}

	async function saveGoal() {
		const goal = parseFloat(goalValue);
		if (isNaN(goal) || goal <= 0) return;
		try {
			await fetch('/api/profile', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ monthly_revenue_goal: goal })
			});
			projectionLoading.set(true);
			const res = await fetch(`/api/projection?scale=${currentScale}`);
			if (res.ok) {
				projectionStore.set(await res.json());
			}
		} catch (e) {
			console.error('Goal save failed:', e);
		} finally {
			projectionLoading.set(false);
		}
	}

	$: goalHint = getGoalHint(projection);

	function getGoalHint(proj: any): { text: string; emoji: string; color: string } | null {
		if (!proj || !proj.summary) return null;
		const goal = proj.summary.goal_year;
		if (goal) return { text: `✓ Atteint en ${goal.year} (à ${goal.age} ans)`, emoji: '🎯', color: 'text-teal-400' };
		const finalPassive = parseFloat(proj.summary.final_passive_monthly || '0');
		const goalNum = parseFloat(goalValue || '0');
		if (goalNum > 0 && finalPassive < goalNum) {
			return { text: `Pas encore atteint — augmentez l'épargne ou ajoutez des projets`, emoji: '⚠️', color: 'text-amber-400' };
		}
		if (!goalValue) return null;
		return null;
	}

	// ── Derived values ─────────────────────────────────────────────────
	$: finalWealth = projection?.summary?.final_wealth || '0';
	$: finalPassive = projection?.summary?.final_passive_monthly || '0';
	$: targetAge = profile?.target_retirement_age || 67;
	$: currentAge = profile?.current_age || 0;
	$: lastYear = projection?.timeline?.[projection.timeline.length - 1];
	$: firstYear = projection?.timeline?.[0];

	// Sprint 5: Post-retirement summary fields
	$: wealthExhaustionAge = projection?.summary?.wealth_exhaustion_age ?? null;
	$: retirementMonthlyIncome = projection?.summary?.retirement_monthly_income || '0';
	$: retirementMonthlyGap = projection?.summary?.retirement_monthly_gap || '0';
	$: hasRetirementPhase = (projection?.timeline || []).some((t: any) => t.is_retirement);

	$: timeline = projection?.timeline || [];
	$: retirementIndex = timeline.findIndex((t: any) => t.is_retirement);
	$: wealthChartData = timeline.map((t: any) => ({ value: parseFloat(t.total_wealth || '0'), isRetirement: t.is_retirement, year: t.year, age: t.age }));
	$: incomeChartData = timeline.map((t: any) => ({ value: parseFloat(t.total_monthly_income || '0'), isRetirement: t.is_retirement, year: t.year, age: t.age }));
	$: goalLineValue = goalValue ? parseFloat(goalValue) : null;

	// ── Milestones ─────────────────────────────────────────────────────
	$: milestones = projection?.summary?.milestones || [];
	const milestoneColors: Record<string, string> = { '100k€': '#22d3ee', '250k€': '#a78bfa', '500k€': '#f59e0b', '1M€': '#10b981' };

	// ── Table data ────────────────────────────────────────────
	$: readiness = projection?.readiness || null;
	$: filteredTimeline = filterTimeline(projection?.timeline || []);
	function filterTimeline(timeline: any[]): any[] {
		if (!timeline.length) return [];
		return timeline.filter((_: any, i: number) => i % 5 === 0 || i === timeline.length - 1);
	}

	$: insightState = getInsightState(projection, goalValue);
	function getInsightState(proj: any, goalStr: string): 'reached' | 'gap' | 'nogoal' {
		if (!proj?.summary) return 'nogoal';
		const hasGoal = goalStr && parseFloat(goalStr) > 0;
		if (!hasGoal) return 'nogoal';
		if (proj.summary.goal_year) return 'reached';
		return 'gap';
	}

	// ── Scenario comparison (TASK-5.7) ────────────────────────────────
	let scenarioOpen = false;
	let scenarioLoading = false;
	let scenarioResult: any = null;
	let scenarioPanel: ScenarioPanel;

	function openScenario() {
		scenarioOpen = true;
		const totalSavings = profile?.allocations
			? profile.allocations.reduce((sum: number, a: any) => sum + (a.monthly_contribution || 0), 0)
			: 0;
		if (scenarioPanel) {
			scenarioPanel.initFromProfile(profile, totalSavings);
		}
	}

	async function handleCompare(e: CustomEvent) {
		scenarioLoading = true;
		try {
			const res = await fetch('/api/projection/compare', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					base_scale: currentScale,
					overrides: e.detail.overrides,
				}),
			});
			if (res.ok) {
				scenarioResult = await res.json();
			}
		} catch (err) {
			console.error('Scenario compare failed:', err);
		} finally {
			scenarioLoading = false;
		}
	}

	function handleScenarioReset() {
		scenarioResult = null;
	}

	async function handleScenarioApply() {
		if (!scenarioResult?.scenario?.summary) return;
		projectionStore.set(scenarioResult.scenario);
		scenarioOpen = false;
		scenarioResult = null;
	}

	// ── Lifeycle Alerts (TASK-6.9) ────────────────────────────────────
	let lifecycleAlerts: any[] = [];
	let alertsLoading = false;

	async function loadAlerts() {
		alertsLoading = true;
		try {
			const res = await fetch(`/api/projection/alerts?scale=${currentScale}`);
			if (res.ok) {
				const data = await res.json();
				lifecycleAlerts = data.alerts || [];
			}
		} catch (e) {
			console.error('Alerts load failed:', e);
		} finally {
			alertsLoading = false;
		}
	}

	// ── Sensitivity Analysis (TASK-6.7) ──────────────────────────────
	let sensitivityData: any = null;
	let sensitivityLoading = false;

	async function loadSensitivity() {
		sensitivityLoading = true;
		try {
			const res = await fetch(`/api/projection/sensitivity?scale=${currentScale}`);
			if (res.ok) {
				sensitivityData = await res.json();
			}
		} catch (e) {
			console.error('Sensitivity load failed:', e);
		} finally {
			sensitivityLoading = false;
		}
	}

	// ── Year Drill-Down (TASK-6.10) ──────────────────────────────────
	let drillDownYear: number | null = null;
	let drillDownData: any = null;
	let drillDownLoading = false;

	async function loadDrillDown(year: number) {
		drillDownLoading = true;
		drillDownYear = year;
		try {
			const res = await fetch(`/api/projection/year/${year}?scale=${currentScale}`);
			if (res.ok) {
				drillDownData = await res.json();
			}
		} catch (e) {
			console.error('Drill-down load failed:', e);
		} finally {
			drillDownLoading = false;
		}
	}

	function closeDrillDown() {
		drillDownYear = null;
		drillDownData = null;
	}

	// Reload Sprint 6 data on scale change
	$: if (currentScale && projection && _s6Loaded) {
		loadAlerts();
		loadSensitivity();
	}

	// ── PDF Export (TASK-5.9) ─────────────────────────────────────────
	let exportLoading = false;

	async function exportPdf() {
		exportLoading = true;
		try {
			const res = await fetch(`/api/projection/export?scale=${currentScale}`);
			if (!res.ok) throw new Error('Export failed');
			const blob = await res.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `horizon-projection-${new Date().toISOString().slice(0, 10)}.pdf`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (err) {
			console.error('PDF export failed:', err);
		} finally {
			exportLoading = false;
		}
	}
</script>

<svelte:head>
	<title>Horizon — Projection à 30 ans</title>
</svelte:head>

<div class="space-y-5" class:opacity-50={loading}>
	<!-- ── Error: no birth date ────────────────────────────────────── -->
	{#if showNoBirthdate}
		<div class="text-center py-20">
			<p class="text-lg text-zinc-400 mb-2">📅 Date de naissance requise</p>
			<p class="text-sm text-zinc-500 mb-4">
				Pour calculer votre horizon, renseignez votre date de naissance dans la page Identité.
			</p>
			<a href="/identity" class="text-teal-400 hover:text-teal-300 text-sm underline">Aller à Identité →</a>
		</div>
	{:else if showApiError}
		<div class="text-center py-20">
			<p class="text-lg text-zinc-400 mb-2">Erreur de calcul</p>
			<p class="text-sm text-zinc-500 mb-4">
				{#if serverError === 'no_session'}
					Votre session a expiré. Veuillez vous reconnecter.
				{:else}
					Impossible de calculer la projection (erreur: {serverError}). Vérifiez que vous avez renseigné votre CA mensuel et votre date de naissance.
				{/if}
			</p>
			<button on:click={() => changeScale(currentScale)} class="text-teal-400 hover:text-teal-300 text-sm underline">Réessayer</button>
		</div>
	{:else if !projection}
		<div class="text-center py-20">
			<p class="text-sm text-zinc-500">Chargement de la projection...</p>
		</div>
	{:else}
		<!-- ── Scale selector + Export + Scenario ──────────────────────── -->
		<div class="flex gap-2">
			{#each SCALES as s}
				<button class="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border {currentScale === s.key ? 'border-zinc-600 bg-zinc-800 text-white' : 'border-zinc-800/40 bg-zinc-900/30 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/20'}"
					on:click={() => changeScale(s.key)}>{s.label}</button>
			{/each}
			<button on:click={openScenario}
				class="px-2.5 py-2 rounded-lg text-xs font-medium border border-zinc-800/40 bg-zinc-900/30 text-zinc-400 hover:text-zinc-300 hover:bg-zinc-800/20 transition-all"
				title="Tester des scénarios (Et si...?)"
			>🔮</button>
			<button on:click={exportPdf} disabled={exportLoading}
				class="px-2.5 py-2 rounded-lg text-xs font-medium border border-zinc-800/40 bg-zinc-900/30 text-zinc-400 hover:text-zinc-300 hover:bg-zinc-800/20 transition-all disabled:opacity-30"
				title="Exporter en PDF"
			>{exportLoading ? '⏳' : '📄'}</button>
		</div>

		<!-- ── Goal input card ────────────────────────────────────────────── -->
		<div class="bg-teal-950/15 border border-teal-900/30 rounded-xl p-4">
			<p class="text-xs font-semibold text-teal-300 mb-2">🎯 Objectif de revenu mensuel à la retraite</p>
			<p class="text-[10px] text-zinc-500 mb-3">Combien voulez-vous toucher (travail + passif + projets) pour ne plus dépendre de personne ?</p>
			<div class="flex gap-2 items-center">
				<input type="number" bind:value={goalValue} placeholder="ex: 4000"
					class="w-28 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 text-sm text-right font-mono text-white focus:border-teal-500/50 focus:outline-none" />
				<span class="text-zinc-500 text-sm">€/mois</span>
				<button on:click={saveGoal} class="px-3 py-1.5 rounded-lg bg-teal-600/80 hover:bg-teal-600 text-xs font-medium text-white transition-colors">Appliquer</button>
			</div>
			{#if goalHint}<p class="text-[10px] mt-2 {goalHint.color}">{goalHint.emoji} {goalHint.text}</p>{/if}
		</div>

		<!-- ── Hero stat cards ────────────────────────────────────────────── -->
		<div class="grid grid-cols-2 gap-3">
			<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
				<p class="text-[9px] text-zinc-500 uppercase tracking-wider mb-1">Patrimoine à {targetAge} ans ({lastYear?.year || '—'})</p>
				<p class="text-2xl font-bold text-teal-400 font-mono">{fmtK(finalWealth)}</p>
			</div>
			<div class="bg-emerald-950/10 border border-emerald-900/20 rounded-xl p-4">
				<p class="text-[9px] text-zinc-500 uppercase tracking-wider mb-1">Revenu passif mensuel</p>
				<p class="text-2xl font-bold text-emerald-400 font-mono">{fmt(finalPassive)}</p>
				<p class="text-[9px] text-emerald-600/50 mt-0.5">Règle des 4%</p>
			</div>
			<!-- Sprint 5: Post-retirement — wealth exhaustion or income gap -->
			{#if hasRetirementPhase && wealthExhaustionAge != null}
				<div class="bg-rose-950/10 border border-rose-900/20 rounded-xl p-4 col-span-2">
					<p class="text-[9px] text-zinc-500 uppercase tracking-wider mb-1">Épuisement du patrimoine</p>
					<p class="text-2xl font-bold text-rose-400 font-mono">À {wealthExhaustionAge} ans</p>
					<p class="text-[9px] text-rose-500/70 mt-0.5">Votre épargne sera épuisée. Augmentez vos versements ou réduisez vos dépenses.</p>
				</div>
			{:else if hasRetirementPhase}
				<div class="bg-emerald-950/10 border border-emerald-900/20 rounded-xl p-4 col-span-2">
					<p class="text-[9px] text-zinc-500 uppercase tracking-wider mb-1">Patrimoine à la retraite</p>
					<p class="text-2xl font-bold text-emerald-400 font-mono">Au-delà de 95 ans</p>
					<p class="text-[9px] text-emerald-500/70 mt-0.5">Votre épargne couvre toute la durée de la retraite projetée.</p>
				</div>
			{/if}
		</div>

		<!-- ── Readiness Gauge (TASK-5.5) ─────────────────────────────────── -->
		{#if readiness}
			<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4 flex justify-center">
				<ReadinessGauge
					score={readiness.score}
					label={readiness.label}
					color={readiness.color}
					summary={readiness.summary}
					components={readiness.components}
				/>
			</div>
		{/if}

		<!-- ── Pension Estimate (TASK-6.2) ────────────────────────────────── -->
		{#if pensionEstimate && parseFloat(pensionEstimate.total_monthly || '0') > 0}
			<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
				<p class="text-xs font-semibold text-zinc-300 mb-3">🏛️ Estimation indicative de retraite</p>
				<div class="grid grid-cols-2 gap-3 mb-3">
					<div class="bg-zinc-900/40 rounded-lg p-3 text-center">
						<span class="block text-lg font-bold font-mono text-teal-300">{fmt(pensionEstimate.total_monthly)}</span>
						<span class="text-[10px] text-zinc-500">Pension mensuelle estimée</span>
					</div>
					<div class="bg-zinc-900/40 rounded-lg p-3 text-center">
						<span class="block text-lg font-bold font-mono {pensionEstimate.is_taux_plein ? 'text-emerald-400' : 'text-amber-400'}">{parseFloat(pensionEstimate.taux || '0') * 100}%</span>
						<span class="text-[10px] text-zinc-500">{pensionEstimate.is_taux_plein ? 'Taux plein' : 'Décote'}</span>
					</div>
				</div>
				<div class="text-[10px] text-zinc-400 space-y-1 mb-2">
					<div class="flex justify-between"><span>Retraite de base</span><span class="font-mono">{fmt(pensionEstimate.base_monthly)}</span></div>
					<div class="flex justify-between"><span>Complémentaire</span><span class="font-mono">{fmt(pensionEstimate.complementaire_monthly)}</span></div>
				</div>
				<div class="flex items-center gap-2 text-[10px]">
					<span class="text-zinc-500">{pensionEstimate.trimestres_valides ?? 0} / {pensionEstimate.trimestres_requis ?? 172} trimestres</span>
					<div class="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
						<div class="h-full bg-teal-500 rounded-full" style="width: {Math.min(100, ((pensionEstimate.trimestres_valides ?? 0) / (pensionEstimate.trimestres_requis || 1)) * 100)}%"></div>
					</div>
				</div>
				<p class="text-[9px] text-zinc-600 mt-2">Estimation basée sur votre parcours déclaré. Consultez info-retraite.fr pour un calcul officiel.</p>
			</div>
		{/if}

		<!-- ── Net Worth Snapshot (TASK-6.5) ───────────────────────────────── -->
		{#if netWorth}
			<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
				<p class="text-xs font-semibold text-zinc-300 mb-3">💰 Bilan patrimonial</p>
				<div class="text-center mb-3">
					<span class="block text-2xl font-bold font-mono text-teal-300">{fmt(netWorth.net_worth)}</span>
					<span class="text-[10px] text-zinc-500">Patrimoine net estimé</span>
				</div>
				<div class="grid grid-cols-2 gap-2 text-[10px]">
					<div class="bg-zinc-900/40 rounded-lg p-2">
						<span class="text-zinc-500">Actifs</span>
						<span class="block font-mono text-teal-300">{fmt(netWorth.total_assets)}</span>
					</div>
					<div class="bg-zinc-900/40 rounded-lg p-2">
						<span class="text-zinc-500">Dettes</span>
						<span class="block font-mono text-rose-400">{fmt(netWorth.total_debts)}</span>
					</div>
				</div>
				{#if netWorth.note}
					<p class="text-[9px] text-zinc-500 mt-2">{netWorth.note}</p>
				{/if}
			</div>
		{/if}

		<!-- ── Wealth chart ────────────────────────────────────────────────── -->
		<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
			<p class="text-xs font-semibold text-zinc-300 mb-2">Trajectoire patrimoine</p>
			<AreaChart data={wealthChartData} height={140} color="#2dd4bf" goalLine={null}
				startLabel="{firstYear?.year || ''} ({firstYear?.age || ''} ans)"
				endLabel="{lastYear?.year || ''} ({lastYear?.age || ''} ans)"
				showRetirementMarker={hasRetirementPhase} retirementIndex={retirementIndex > -1 ? retirementIndex : -1} />
		</div>

		<!-- ── Income chart ────────────────────────────────────────────────── -->
		<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
			<p class="text-xs font-semibold text-zinc-300 mb-2">Revenu total mensuel (travail + passif + projets)</p>
			<AreaChart data={incomeChartData} height={120} color="#10b981" goalLine={goalLineValue}
				startLabel="{fmt(firstYear?.total_monthly_income || '0')}/mois"
				endLabel="{fmt(lastYear?.total_monthly_income || '0')}/mois"
				showRetirementMarker={hasRetirementPhase} retirementIndex={retirementIndex > -1 ? retirementIndex : -1} />
			{#if goalLineValue}<div class="text-center mt-1"><span class="text-[9px] text-amber-400/70">Objectif: {fmt(goalLineValue)}</span></div>{/if}
		</div>

		<!-- ── Milestones ──────────────────────────────────────────────────── -->
		<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
			<p class="text-xs font-semibold text-zinc-300 mb-3">Jalons</p>
			{#if milestones.length === 0}
				<p class="text-[10px] text-zinc-500">Aucun jalon atteint sur cette période. Augmentez votre épargne mensuelle pour voir les jalons apparaître.</p>
			{:else}
				<div class="relative pl-4">
					<div class="absolute left-2 top-2 bottom-2 w-px bg-zinc-800"></div>
					{#each milestones as m}
						<div class="flex items-center gap-3 py-2 relative z-10">
							<div class="w-4 h-4 rounded-full border-2 bg-zinc-950 flex items-center justify-center {m.label === '100k€' ? 'border-cyan-400' : m.label === '250k€' ? 'border-purple-400' : m.label === '500k€' ? 'border-amber-400' : 'border-emerald-400'}">
								<div class="w-1.5 h-1.5 rounded-full" style="background-color: {milestoneColors[m.label] || '#fff'}"></div>
							</div>
							<span class="text-sm font-mono font-bold" style="color: {milestoneColors[m.label] || '#fff'}">{m.label}</span>
							<span class="text-xs text-zinc-500">→ {m.year} (à {m.age} ans)</span>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- ── Projection table ────────────────────────────────────────────── -->
		<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4 overflow-x-auto">
			<p class="text-xs font-semibold text-zinc-300 mb-2">Projection détaillée</p>
			<table class="w-full text-[10px]">
				<thead>
					<tr class="border-b border-zinc-800 text-[9px] uppercase text-zinc-500">
						<th class="py-1 text-left">An</th><th class="py-1 text-right">Âge</th><th class="py-1 text-right">CA brut</th>
						<th class="py-1 text-right">Cotis.</th><th class="py-1 text-right">Cotis.%</th><th class="py-1 text-right">Vie</th>
						<th class="py-1 text-right">Enfants</th><th class="py-1 text-right">Projets</th><th class="py-1 text-right">Net</th>
						<th class="py-1 text-right">Patrimoine</th><th class="py-1 text-right">Passif/mois</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredTimeline as t}
						<tr class="border-t border-zinc-800/30 hover:bg-zinc-800/10 cursor-pointer" on:click={() => loadDrillDown(t.year)} data-coco-desc={`Cliquer pour voir le détail de l'année ${t.year}`}>
							<td class="py-1 font-mono text-teal-400 underline decoration-dotted">{t.year}</td>
							<td class="py-1 font-mono text-zinc-300 text-right">{t.age}</td>
							<td class="py-1 font-mono text-zinc-300 text-right">{fmtK(t.gross_annual)}</td>
							<td class="py-1 font-mono text-rose-400/70 text-right">{fmtK(t.charges)}</td>
							<td class="py-1 font-mono text-rose-400/50 text-right">{fmtPct(t.ae_rate)}</td>
							<td class="py-1 font-mono text-amber-400/70 text-right">{fmtK(t.base_expenses)}</td>
							<td class="py-1 font-mono text-purple-400/70 text-right">{parseFloat(t.kid_expenses) > 0 ? fmtK(t.kid_expenses) : '—'}</td>
							<td class="py-1 font-mono text-sky-400/70 text-right">
								{#if parseFloat(t.project_income) > 0}+{fmtK(t.project_income)}{:else if parseFloat(t.project_expenses) > 0}-{fmtK(t.project_expenses)}{:else}—{/if}
							</td>
							<td class="py-1 font-mono text-right font-medium {parseFloat(t.net_annual) >= 0 ? 'text-teal-400' : 'text-rose-400'}">{fmtK(t.net_annual)}</td>
							<td class="py-1 font-mono font-bold text-white text-right">{fmtK(t.total_wealth)}</td>
							<td class="py-1 font-mono text-emerald-400 text-right">{fmt(t.passive_monthly)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!-- ── Sensitivity Analysis (TASK-6.7) ────────────────────────────── -->
		{#if sensitivityData?.parameters?.length}
			<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
				<p class="text-xs font-semibold text-zinc-300 mb-3">🔍 Qu'est-ce qui compte le plus ?</p>
				<p class="text-[10px] text-zinc-500 mb-3">{sensitivityData.top_lever_narrative || 'Analyse de sensibilité sur les leviers financiers.'}</p>
				<div class="space-y-2">
					{#each sensitivityData.parameters as param}
						<div class="flex items-center gap-3">
							<span class="text-[10px] text-zinc-400 w-40 text-right truncate" title={param.label}>{param.label}</span>
							<div class="flex-1 h-3 bg-zinc-900 rounded-full overflow-hidden">
								<div
									class="h-full rounded-full {parseFloat(param.delta_wealth || '0') > 0 ? 'bg-teal-500' : 'bg-rose-500'}"
									style="width: {Math.min(100, Math.abs(parseFloat(param.delta_pct || '0')) * 2)}%"
								></div>
							</div>
							<span class="text-[10px] font-mono w-24 text-right {parseFloat(param.delta_wealth || '0') > 0 ? 'text-teal-400' : 'text-rose-400'}">
								{parseFloat(param.delta_wealth || '0') > 0 ? '+' : ''}{fmtK(param.delta_wealth)}
							</span>
							<span class="text-[9px] text-zinc-600 w-10 text-right">#{param.rank}</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- ── Lifeycle Alerts (TASK-6.9) ─────────────────────────────────── -->
		{#if lifecycleAlerts.length > 0}
			<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
				<p class="text-xs font-semibold text-zinc-300 mb-3">📅 Événements à venir</p>
				<div class="space-y-2 max-h-80 overflow-y-auto">
					{#each lifecycleAlerts as alert}
						<div
							class="flex items-start gap-2 p-2 rounded-lg border {alert.severity === 'warning' ? 'bg-rose-950/20 border-rose-800/30' : alert.severity === 'action' ? 'bg-amber-950/20 border-amber-800/30' : 'bg-zinc-900/40 border-zinc-800/30'}"
							data-coco-desc="Alerte {alert.alert_type} : {alert.title}"
						>
							<span class="text-xs mt-0.5">
								{alert.severity === 'warning' ? '🔴' : alert.severity === 'action' ? '🟡' : '🔵'}
							</span>
							<div class="flex-1 min-w-0">
								<p class="text-[11px] text-zinc-200 font-medium">{alert.title}</p>
								<p class="text-[10px] text-zinc-400">{alert.description}</p>
								{#if alert.action_label}
									<a
										href={alert.action_link || '#'}
										class="text-[10px] text-teal-400 hover:text-teal-300 underline mt-1 inline-block"
									>{alert.action_label}</a>
								{/if}
							</div>
							<span class="text-[10px] text-zinc-500 flex-shrink-0">{alert.year} ({alert.age} ans)</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- ── Year Drill-Down Panel (TASK-6.10) ───────────────────────────── -->
		{#if drillDownData}
			<div class="bg-zinc-800/30 border border-teal-800/30 rounded-xl p-4">
				<div class="flex items-center justify-between mb-3">
					<p class="text-xs font-semibold text-teal-300">🔎 Détail {drillDownData.year} (à {drillDownData.age} ans) — {drillDownData.phase === 'post-retirement' ? 'Post-retraite' : 'Accumulation'}</p>
					<button class="text-zinc-500 hover:text-zinc-300 text-xs" on:click={closeDrillDown}>✕</button>
				</div>

				<div class="grid grid-cols-2 gap-3 mb-3">
					<div class="bg-zinc-900/40 rounded-lg p-3">
						<p class="text-[9px] text-zinc-500 mb-1">Revenus</p>
						<div class="text-[10px] text-zinc-300 space-y-0.5">
							<div class="flex justify-between"><span>CA brut</span><span class="font-mono">{fmtK(drillDownData.income.gross_ca)}</span></div>
							<div class="flex justify-between"><span>CAF</span><span class="font-mono">{fmt(drillDownData.income.caf)}</span></div>
							<div class="flex justify-between"><span>Crédit d'impôt</span><span class="font-mono">{fmt(drillDownData.income.cesu_credit)}</span></div>
							{#if parseFloat(drillDownData.income.pension || '0') > 0}
								<div class="flex justify-between"><span>Pension</span><span class="font-mono">{fmt(drillDownData.income.pension)}</span></div>
							{/if}
							<div class="flex justify-between font-medium text-teal-300"><span>Total</span><span class="font-mono">{fmtK(drillDownData.income.total)}</span></div>
						</div>
					</div>
					<div class="bg-zinc-900/40 rounded-lg p-3">
						<p class="text-[9px] text-zinc-500 mb-1">Dépenses</p>
						<div class="text-[10px] text-zinc-300 space-y-0.5">
							<div class="flex justify-between"><span>Cotisations</span><span class="font-mono text-rose-400">{fmtK(drillDownData.charges.ae_cotisations)}</span></div>
							<div class="flex justify-between"><span>Base ({drillDownData.expenses.base_total_monthly}/mois)</span><span class="font-mono text-amber-400">{fmtK(drillDownData.expenses.base_total_annual)}</span></div>
							{#if drillDownData.loans?.length}
								{#each drillDownData.loans as loan}
									<div class="flex justify-between"><span>{loan.label}</span><span class="font-mono text-purple-400">{loan.monthly}/mois</span></div>
								{/each}
							{/if}
							{#if drillDownData.life_entities?.length}
								{#each drillDownData.life_entities as le}
									<div class="flex justify-between"><span>{le.name} ({le.type})</span><span class="font-mono">{fmt(le.subtotal)}</span></div>
								{/each}
							{/if}
							<div class="flex justify-between font-medium text-rose-400"><span>Total sorties</span><span class="font-mono">{fmtK(drillDownData.summary.total_outgoing)}</span></div>
						</div>
					</div>
				</div>

				{#if drillDownData.investments?.contributions && Object.keys(drillDownData.investments.contributions).length > 0}
					<div class="bg-zinc-900/40 rounded-lg p-3 mb-3">
						<p class="text-[9px] text-zinc-500 mb-1">Investissements</p>
						<div class="text-[10px] text-zinc-300 space-y-0.5">
							{#each Object.keys(drillDownData.investments.contributions) as vk}
								<div class="flex justify-between"><span>{vk}</span><span class="font-mono">{fmt(drillDownData.investments.contributions[vk])} versé / {fmt(drillDownData.investments.returns[vk])} retour</span></div>
							{/each}
						</div>
					</div>
				{/if}

				<div class="bg-zinc-900/40 rounded-lg p-3">
					<div class="flex justify-between items-center">
						<span class="text-[10px] text-zinc-400">Résultat net</span>
						<span class="text-sm font-mono font-bold {drillDownData.summary.net_status === 'surplus' ? 'text-teal-400' : 'text-rose-400'}">
							{fmtK(drillDownData.summary.net)}
						</span>
					</div>
					<p class="text-[10px] text-zinc-500 mt-1">{drillDownData.summary.explanation}</p>
				</div>
			</div>
		{/if}

		<!-- ── Insights Engine (TASK-5.4) ─────────────────────────────────── -->
		<InsightCards insights={projection?.insights || []} />

		<!-- ── Insight cards ───────────────────────────────────────────────── -->
		<div class="space-y-3">
			{#if insightState === 'reached'}
				<div class="bg-emerald-950/15 border border-emerald-900/30 rounded-xl p-4">
					<p class="text-xs font-semibold text-emerald-300 mb-1">🏆 Objectif atteint.</p>
					<p class="text-[10px] text-emerald-300/80">À {targetAge} ans, vos revenus passifs ({fmt(finalPassive)}/mois) couvrent votre objectif. Vous n'avez pas besoin de la retraite d'État.</p>
				</div>
			{:else if insightState === 'gap'}
				<div class="bg-amber-950/15 border border-amber-900/30 rounded-xl p-4">
					<p class="text-xs font-semibold text-amber-300 mb-1">⚠️ Gap à combler.</p>
					<p class="text-[10px] text-amber-300/80">
						Vos revenus passifs projetés ({fmt(finalPassive)}/mois) sont en dessous de votre objectif ({fmt(goalValue)}). Pistes :
						<a href="/savings" class="underline text-amber-400 hover:text-amber-300">augmenter l'épargne mensuelle</a>,
						<a href="/projects" class="underline text-amber-400 hover:text-amber-300">ajouter un projet immobilier</a>, ou
						<a href="/projects" class="underline text-amber-400 hover:text-amber-300">changer de statut juridique</a>.
					</p>
				</div>
			{:else}
				<div class="bg-teal-950/10 border border-teal-900/20 rounded-xl p-4">
					<p class="text-xs font-semibold text-teal-300/70 mb-1">💡 Définissez un objectif.</p>
					<p class="text-[10px] text-teal-300/50">Sans objectif, la projection montre l'évolution mais pas la destination. Combien voulez-vous toucher par mois à la retraite ? Renseignez-le ci-dessus.</p>
				</div>
			{/if}

			<div class="bg-zinc-900/40 border border-zinc-800/40 rounded-xl p-3">
				<p class="text-[10px] text-zinc-500 leading-relaxed">⚖️ Simulateur uniquement. Ne constitue pas un conseil financier, fiscal ou juridique. Rendements historiques moyens, cotisations projetées sur tendances législatives. Les rendements passés ne préjugent pas des rendements futurs.</p>
			</div>
		</div>
	{/if}
</div>

<!-- ── Scenario Panel (TASK-5.7) ────────────────────────────────── -->
<ScenarioPanel
	bind:this={scenarioPanel}
	open={scenarioOpen}
	loading={scenarioLoading}
	currentScale={currentScale}
	baseSummary={projection?.summary}
	scenarioResult={scenarioResult}
	on:compare={handleCompare}
	on:reset={handleScenarioReset}
	on:apply={handleScenarioApply}
	on:close={() => { scenarioOpen = false; scenarioResult = null; }}
/>