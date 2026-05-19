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
	$: spousePension = (data as any).spousePension ?? null;
	$: householdPensionMonthly = (data as any).householdPensionMonthly ?? null;
	$: spouse = (data as any).spouse ?? null;
	$: hasSpouse = spouse != null;
	$: netWorth = (data as any).netWorth ?? null;
	$: projections = (data as any).projections ?? null;
	$: incomeSources = (data as any).incomeSources ?? [];
	$: adviceData = (data as any).advice ?? { advice: [], count: 0 };
	$: adviceList = adviceData.advice || [];
	$: actionPlan = (data as any).actionPlan ?? { actions: [], count: 0, month: '' };
	$: actionItems = actionPlan.actions || [];

	// ── TASK-7.14: Confidence band data ─────────────────────────────────
	$: optTimeline = projections?.optimistic?.timeline || [];
	$: modTimeline = projections?.moderate?.timeline || timeline;
	$: pesTimeline = confidenceAdjustedPessimistic(projections?.pessimistic?.timeline || [], incomeSources);

	function confidenceAdjustedPessimistic(pesTimeline: any[], sources: any[]): any[] {
		if (!pesTimeline.length || !sources.length) return pesTimeline;
		// Compute total low-confidence monthly income
		const lowConfidenceMonthly = sources
			.filter((s: any) => s.confidence === 'low' && s.is_active)
			.reduce((sum: number, s: any) => {
				const amt = parseFloat(s.amount || '0');
				if (s.frequency === 'annual') return sum + amt / 12;
				if (s.frequency === 'one_time') return sum;
				return sum + amt;
			}, 0);
		const totalMonthly = sources
			.filter((s: any) => s.is_active && s.frequency === 'monthly')
			.reduce((sum: number, s: any) => sum + parseFloat(s.amount || '0'), 0);

		if (totalMonthly === 0) return pesTimeline;
		const uncertaintyFactor = Math.min(0.15, (lowConfidenceMonthly / totalMonthly) * 0.2);
		if (uncertaintyFactor <= 0) return pesTimeline;

		return pesTimeline.map((t: any) => ({
			...t,
			total_wealth: String(parseFloat(t.total_wealth || '0') * (1 - uncertaintyFactor)),
			total_monthly_income: String(parseFloat(t.total_monthly_income || '0') * (1 - uncertaintyFactor)),
		}));
	}

	// Band chart SVG computation helpers
	interface BandDataPoint { value: number; year?: number; age?: number; isRetirement?: boolean; }
	function computeBandChart(
		optData: BandDataPoint[], modData: BandDataPoint[], pesData: BandDataPoint[],
		w: number, h: number, top: number, bot: number
	) {
		const padding = { left: 50, right: 10, top: 8, bottom: 18 };
		const cw = w - padding.left - padding.right;
		const ch = h - padding.top - padding.bottom;

		const allVals = [...optData, ...modData, ...pesData].map(d => d.value);
		const max = Math.max(...allVals, 0);
		const min = Math.min(...allVals, 0);
		const range = max - min || 1;

		const toY = (v: number) => padding.top + ch - ((v - min) / range) * ch * 0.9 - ch * 0.05;
		const toX = (i: number, total: number) => padding.left + (i / Math.max(total - 1, 1)) * cw;

		const topPts = optData.map((d, i) => `${toX(i, optData.length)},${toY(d.value)}`).join(' ');
		const bottomPts = pesData.map((d, i) => `${toX(i, pesData.length)},${toY(d.value)}`).reverse().join(' ');
		const bandPolygon = `${topPts} ${bottomPts}`;

		const modLine = modData.map((d, i) => `${toX(i, modData.length)},${toY(d.value)}`).join(' ');
		const optLine = optData.map((d, i) => `${toX(i, optData.length)},${toY(d.value)}`).join(' ');
		const pesLine = pesData.map((d, i) => `${toX(i, pesData.length)},${toY(d.value)}`).join(' ');

		return { bandPolygon, modLine, optLine, pesLine, padding, cw, ch, max, min, toX, toY };
	}

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
	$: finalWealth = projection?.summary?.final_liquid_wealth || projection?.summary?.final_wealth || '0';

	$: finalTotalWealth = projection?.summary?.final_wealth || '0';
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

		<!-- ── Action Plan (TASK-7.17) ───────────────────────────────────── -->
		{#if actionItems.length > 0}
			<div class="bg-zinc-800/30 border border-teal-800/30 rounded-xl p-4">
				<div class="flex items-center justify-between mb-3">
					<p class="text-xs font-semibold text-zinc-300">📋 Plan d'action — {actionPlan.month || 'Ce mois'}</p>
					<span class="text-[9px] text-zinc-500">{actionPlan.count || actionItems.length} action{actionItems.length > 1 ? 's' : ''}</span>
				</div>
				<div class="space-y-2">
					{#each actionItems as action}
						<div class="flex items-start gap-3 p-2.5 bg-zinc-900/40 border border-zinc-700/20 rounded-lg">
							<span class="text-xs mt-0.5 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center
								{action.priority === 1 ? 'bg-rose-900/40 text-rose-400' :
								 action.priority === 2 ? 'bg-amber-900/40 text-amber-400' :
								 'bg-zinc-800 text-zinc-400'}">
								{action.priority}
							</span>
							<div class="flex-1 min-w-0">
								<p class="text-xs text-zinc-200">{action.title}</p>
								<p class="text-[10px] text-zinc-500 mt-0.5">{action.detail}</p>
							</div>
							{#if action.amount}
								<span class="text-xs font-mono text-teal-400 whitespace-nowrap">{fmt(action.amount)}</span>
							{/if}
							{#if action.link_to}
								<a href={action.link_to} class="text-[10px] text-teal-400 hover:text-teal-300 whitespace-nowrap flex-shrink-0">→</a>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		{/if}

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
				<p class="text-[9px] text-zinc-500 uppercase tracking-wider mb-1">Épargne liquide à {targetAge} ans</p>
				<p class="text-2xl font-bold text-teal-400 font-mono">{fmtK(finalWealth)}</p>
				{#if finalTotalWealth && finalTotalWealth !== finalWealth}
					<p class="text-[9px] text-zinc-600 mt-0.5">+ {fmtK(parseFloat(finalTotalWealth) - parseFloat(finalWealth))} immobilier = {fmtK(finalTotalWealth)} total</p>
				{/if}
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

		<!-- ── Actions recommandées (TASK-7.15) ─────────────────────────────── -->
		{#if adviceList.length > 0}
			<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
				<p class="text-xs font-semibold text-zinc-300 mb-3">🎯 Actions recommandées</p>
				<div class="space-y-2">
					{#each adviceList as advice}
						<div class="p-3 bg-zinc-900/40 border border-zinc-700/30 rounded-lg">
							<div class="flex items-start gap-2">
								<span class="text-sm mt-0.5">
									{advice.priority === 1 ? '🔴' : advice.priority === 2 ? '🟡' : '🟢'}
								</span>
								<div class="flex-1">
									<p class="text-xs text-zinc-200 font-medium">{advice.title}</p>
									<p class="text-[10px] text-zinc-500 mt-0.5">{advice.description}</p>
									<p class="text-[10px] text-teal-400 mt-1">{advice.impact_text}</p>
									<p class="text-[10px] text-zinc-400 mt-0.5 italic">{advice.action_text}</p>
								</div>
								{#if advice.link_to}
									<a href={advice.link_to} class="text-[10px] text-teal-400 hover:text-teal-300 whitespace-nowrap">
										Configurer →
									</a>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- ── Pension Estimate (TASK-6.2 / TASK-7.7) ─────────────────── -->
		{#if pensionEstimate && parseFloat(pensionEstimate.total_monthly || '0') > 0}
			<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
				<p class="text-xs font-semibold text-zinc-300 mb-3">
					🏛️ Estimation indicative de retraite
					{#if hasSpouse} — foyer{/if}
				</p>
				<!-- User pension -->
				<div class="grid grid-cols-2 gap-3 mb-3">
					<div class="bg-zinc-900/40 rounded-lg p-3 text-center">
						<span class="block text-lg font-bold font-mono text-teal-300">{fmt(pensionEstimate.total_monthly)}</span>
						<span class="text-[10px] text-zinc-500">Pension {hasSpouse ? '(vous)' : 'mensuelle estimée'}</span>
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

				<!-- Spouse pension (TASK-7.7) -->
				{#if spousePension && parseFloat(spousePension.total_monthly || '0') > 0}
					<div class="mt-3 pt-3 border-t border-zinc-700/40">
						<p class="text-[10px] text-purple-300 font-medium mb-2">
							💑 Conjoint(e) — {spouse?.first_name || 'sans nom'}
							{#if spousePension.includes_cc_trimestres > 0}
								<span class="text-purple-400/70"> (CC: {spousePension.includes_cc_trimestres} trim.)</span>
							{/if}
						</p>
						<div class="grid grid-cols-2 gap-2 mb-2">
							<div class="bg-purple-950/20 rounded p-2 text-center">
								<span class="block font-mono font-bold text-purple-300">{fmt(spousePension.total_monthly)}</span>
								<span class="text-[9px] text-zinc-500">Pension conjoint(e)</span>
							</div>
							<div class="bg-purple-950/20 rounded p-2 text-center">
								<span class="block font-mono font-bold {spousePension.is_taux_plein ? 'text-emerald-400' : 'text-amber-400'}">{parseFloat(spousePension.taux || '0') * 100}%</span>
								<span class="text-[9px] text-zinc-500">{spousePension.is_taux_plein ? 'Taux plein' : 'Décote'}</span>
							</div>
						</div>
						<div class="flex items-center gap-2 text-[9px]">
							<span class="text-zinc-500">{spousePension.trimestres_valides ?? 0} / {spousePension.trimestres_requis ?? 172} trimestres</span>
							<div class="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
								<div class="h-full bg-purple-500 rounded-full" style="width: {Math.min(100, ((spousePension.trimestres_valides ?? 0) / (spousePension.trimestres_requis || 1)) * 100)}%"></div>
							</div>
						</div>
					</div>

					<!-- Household total -->
					{#if householdPensionMonthly}
						<div class="mt-2 pt-2 border-t border-zinc-700/30 flex justify-between items-center">
							<span class="text-[10px] text-zinc-300 font-medium">Total foyer</span>
							<span class="font-mono font-bold text-teal-300">{fmt(householdPensionMonthly)}/mois</span>
						</div>
					{/if}
				{/if}

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

		<!-- ── Wealth chart with confidence band (TASK-7.14) ──────────────── -->
		<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
			<p class="text-xs font-semibold text-zinc-300 mb-2">
				Trajectoire patrimoine
				<span class="text-[9px] text-zinc-500 font-normal ml-2">⛅ bande de confiance</span>
			</p>
			{#if projections?.optimistic?.timeline && projections?.pessimistic?.timeline}
				{@const wealthOpt = optTimeline.map((t: any) => ({ value: parseFloat(t.total_wealth || '0'), year: t.year }))}
				{@const wealthMod = modTimeline.map((t: any) => ({ value: parseFloat(t.total_wealth || '0'), year: t.year }))}
				{@const wealthPes = pesTimeline.map((t: any) => ({ value: parseFloat(t.total_wealth || '0'), year: t.year }))}
				{@const wc = computeBandChart(wealthOpt, wealthMod, wealthPes, 400, 140, 8, 18)}
				<svg viewBox="0 0 400 140" class="w-full" preserveAspectRatio="xMidYMid meet" style="height:140px">
					<defs>
						<linearGradient id="wealthBand" x1="0" y1="0" x2="0" y2="1">
							<stop offset="0%" stop-color="#10b981" stop-opacity="0.12" />
							<stop offset="100%" stop-color="#f43f5e" stop-opacity="0.04" />
						</linearGradient>
					</defs>
					<!-- Confidence band -->
					<polygon points={wc.bandPolygon} fill="url(#wealthBand)" opacity="0.5" />
					<!-- Pessimistic line -->
					<polyline points={wc.pesLine} fill="none" stroke="#f43f5e" stroke-width="1" stroke-dasharray="4,3" opacity="0.3" />
					<!-- Optimistic line -->
					<polyline points={wc.optLine} fill="none" stroke="#10b981" stroke-width="1" stroke-dasharray="4,3" opacity="0.3" />
					<!-- Moderate line (primary) -->
					<polyline points={wc.modLine} fill="none" stroke="#2dd4bf" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
					<!-- X-axis labels -->
					<text x="{wc.padding.left}" y="140-3" fill="#71717a" font-size="7" font-family="JetBrains Mono, monospace" text-anchor="start">{firstYear?.year || ''}</text>
					<text x="{wc.padding.left + wc.cw}" y="140-3" fill="#71717a" font-size="7" font-family="JetBrains Mono, monospace" text-anchor="end">{lastYear?.year || ''}</text>
				</svg>
			{:else}
				<AreaChart data={wealthChartData} height={140} color="#2dd4bf" goalLine={null}
					startLabel="{firstYear?.year || ''} ({firstYear?.age || ''} ans)"
					endLabel="{lastYear?.year || ''} ({lastYear?.age || ''} ans)"
					showRetirementMarker={hasRetirementPhase} retirementIndex={retirementIndex > -1 ? retirementIndex : -1} />
			{/if}
		</div>

		<!-- ── Income chart with confidence band (TASK-7.14) ──────────────── -->
		<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
			<p class="text-xs font-semibold text-zinc-300 mb-2">Revenu total mensuel (travail + passif + projets)</p>
			{#if projections?.optimistic?.timeline && projections?.pessimistic?.timeline}
				{@const incOpt = optTimeline.map((t: any) => ({ value: parseFloat(t.total_monthly_income || '0'), year: t.year }))}
				{@const incMod = modTimeline.map((t: any) => ({ value: parseFloat(t.total_monthly_income || '0'), year: t.year }))}
				{@const incPes = pesTimeline.map((t: any) => ({ value: parseFloat(t.total_monthly_income || '0'), year: t.year }))}
				{@const ic = computeBandChart(incOpt, incMod, incPes, 400, 120, 8, 18)}
				<svg viewBox="0 0 400 120" class="w-full" preserveAspectRatio="xMidYMid meet" style="height:120px">
					<defs>
						<linearGradient id="incomeBand" x1="0" y1="0" x2="0" y2="1">
							<stop offset="0%" stop-color="#10b981" stop-opacity="0.12" />
							<stop offset="100%" stop-color="#f43f5e" stop-opacity="0.04" />
						</linearGradient>
					</defs>
					<!-- Confidence band -->
					<polygon points={ic.bandPolygon} fill="url(#incomeBand)" opacity="0.5" />
					<!-- Pessimistic line -->
					<polyline points={ic.pesLine} fill="none" stroke="#f43f5e" stroke-width="1" stroke-dasharray="4,3" opacity="0.3" />
					<!-- Optimistic line -->
					<polyline points={ic.optLine} fill="none" stroke="#10b981" stroke-width="1" stroke-dasharray="4,3" opacity="0.3" />
					<!-- Moderate line (primary) -->
					<polyline points={ic.modLine} fill="none" stroke="#10b981" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
					<!-- Goal line -->
					{#if goalLineValue}
						{@const goalY = ic.padding.top + ic.ch - ((goalLineValue - ic.min) / (ic.max - ic.min || 1)) * ic.ch * 0.9 - ic.ch * 0.05}
						<line x1={ic.padding.left} y1={goalY} x2={ic.padding.left + ic.cw} y2={goalY}
							stroke="#f59e0b" stroke-width="1" stroke-dasharray="6,4" opacity="0.6" />
						<text x={ic.padding.left + ic.cw + 2} y={goalY + 3} fill="#f59e0b"
							font-size="8" font-family="JetBrains Mono, monospace">Obj.</text>
					{/if}
					<!-- X-axis labels -->
					<text x="{ic.padding.left}" y="120-3" fill="#71717a" font-size="7" font-family="JetBrains Mono, monospace" text-anchor="start">{firstYear?.year || ''}</text>
					<text x="{ic.padding.left + ic.cw}" y="120-3" fill="#71717a" font-size="7" font-family="JetBrains Mono, monospace" text-anchor="end">{lastYear?.year || ''}</text>
				</svg>
				{#if goalLineValue}<div class="text-center mt-1"><span class="text-[9px] text-amber-400/70">Objectif: {fmt(goalLineValue)}</span></div>{/if}
			{:else}
				<AreaChart data={incomeChartData} height={120} color="#10b981" goalLine={goalLineValue}
					startLabel="{fmt(firstYear?.total_monthly_income || '0')}/mois"
					endLabel="{fmt(lastYear?.total_monthly_income || '0')}/mois"
					showRetirementMarker={hasRetirementPhase} retirementIndex={retirementIndex > -1 ? retirementIndex : -1} />
				{#if goalLineValue}<div class="text-center mt-1"><span class="text-[9px] text-amber-400/70">Objectif: {fmt(goalLineValue)}</span></div>{/if}
			{/if}
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
						<th class="py-1 text-right" title="Cotisations URSSAF + CFE">Cotis.+CFE</th><th class="py-1 text-right">Cotis.%</th><th class="py-1 text-right">Vie</th>
						<th class="py-1 text-right">Enfants</th><th class="py-1 text-right">Projets</th><th class="py-1 text-right">Net</th>
						<th class="py-1 text-right">Patrimoine</th><th class="py-1 text-right">Retraite/mois</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredTimeline as t}
						<tr class="border-t border-zinc-800/30 hover:bg-zinc-800/10 cursor-pointer" on:click={() => loadDrillDown(t.year)} data-coco-desc={`Cliquer pour voir le détail de l'année ${t.year}`}>
							<td class="py-1 font-mono text-teal-400 underline decoration-dotted">{t.year}</td>
							<td class="py-1 font-mono text-zinc-300 text-right">{t.age}</td>
							<td class="py-1 font-mono text-zinc-300 text-right">{fmtK(t.gross_annual)}</td>
							<td class="py-1 font-mono text-rose-400/70 text-right" title="URSSAF {fmtK(t.charges)} + CFE {fmtK(t.cfe)}">{fmtK(String(parseFloat(t.charges || '0') + parseFloat(t.cfe || '0')))}</td>
							<td class="py-1 font-mono text-rose-400/50 text-right">{fmtPct(t.ae_rate)}</td>
							<td class="py-1 font-mono text-amber-400/70 text-right">{fmtK(t.base_expenses)}</td>
							<td class="py-1 font-mono text-purple-400/70 text-right">{parseFloat(t.kid_expenses) > 0 ? fmtK(t.kid_expenses) : '—'}</td>
							<td class="py-1 font-mono text-sky-400/70 text-right">
								{#if parseFloat(t.project_income) > 0}+{fmtK(t.project_income)}{:else if parseFloat(t.project_expenses) > 0}-{fmtK(t.project_expenses)}{:else}—{/if}
							</td>
							<td class="py-1 font-mono text-right font-medium {parseFloat(t.net_annual) >= 0 ? 'text-teal-400' : 'text-rose-400'}">{fmtK(t.net_annual)}</td>
							<td class="py-1 font-mono font-bold text-white text-right">{fmtK(t.total_wealth)}</td>
							<td class="py-1 font-mono text-emerald-400 text-right">{fmt(parseFloat(t.pension_monthly || '0') + parseFloat(t.passive_monthly || '0'))}</td>
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