<script lang="ts">
	/**
	 * Runway page — the payoff view. 30-year projection engine output rendered as:
	 * scale selector, goal input, hero stats, wealth chart, income chart,
	 * milestones timeline, projection table, insight cards, and disclaimer.
	 */
	import { onMount } from 'svelte';
	import { projectionStore, projectionLoading } from '$lib/stores/projection';
	import AreaChart from '$lib/components/runway/AreaChart.svelte';
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

	// Initialize store from server data
	onMount(() => {
		if (data.projection) {
			projectionStore.set(data.projection);
		}
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

	$: wealthChartData = (projection?.timeline || []).map((t: any) => ({ value: parseFloat(t.total_wealth || '0') }));
	$: incomeChartData = (projection?.timeline || []).map((t: any) => ({ value: parseFloat(t.total_monthly_income || '0') }));
	$: goalLineValue = goalValue ? parseFloat(goalValue) : null;

	// ── Milestones ─────────────────────────────────────────────────────
	$: milestones = projection?.summary?.milestones || [];
	const milestoneColors: Record<string, string> = { '100k€': '#22d3ee', '250k€': '#a78bfa', '500k€': '#f59e0b', '1M€': '#10b981' };

	// ── Table data ────────────────────────────────────────────
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
		<!-- ── Scale selector ─────────────────────────────────────────────── -->
		<div class="flex gap-2">
			{#each SCALES as s}
				<button class="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border {currentScale === s.key ? 'border-zinc-600 bg-zinc-800 text-white' : 'border-zinc-800/40 bg-zinc-900/30 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/20'}"
					on:click={() => changeScale(s.key)}>{s.label}</button>
			{/each}
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
		</div>

		<!-- ── Wealth chart ────────────────────────────────────────────────── -->
		<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
			<p class="text-xs font-semibold text-zinc-300 mb-2">Trajectoire patrimoine</p>
			<AreaChart data={wealthChartData} height={140} color="#2dd4bf" goalLine={null}
				startLabel="{firstYear?.year || ''} ({firstYear?.age || ''} ans)"
				endLabel="{lastYear?.year || ''} ({lastYear?.age || ''} ans)" />
		</div>

		<!-- ── Income chart ────────────────────────────────────────────────── -->
		<div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
			<p class="text-xs font-semibold text-zinc-300 mb-2">Revenu total mensuel (travail + passif + projets)</p>
			<AreaChart data={incomeChartData} height={120} color="#10b981" goalLine={goalLineValue}
				startLabel="{fmt(firstYear?.total_monthly_income || '0')}/mois"
				endLabel="{fmt(lastYear?.total_monthly_income || '0')}/mois" />
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
						<tr class="border-t border-zinc-800/30 hover:bg-zinc-800/10">
							<td class="py-1 font-mono text-zinc-400">{t.year}</td>
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