<script lang="ts">
	/**
	 * Revenue page — Income sources manager, growth presets, 10-year timeline, tax breaks.
	 *
	 * Replaces the single CA input with a multi-source income manager backed by
	 * the income_sources API (TASK-7.5).  Growth presets, CESU/charity, and the
	 * disposable-income waterfall stay unchanged.
	 */
	import { api } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import type { PageData } from './$types';

	export let data: PageData;

	let profile = data.profile ?? {};
	let growthPresets = data.growthPresets ?? {};
	let stats = data.stats ?? { grossMonthly: 0, cotisationsMonthly: 0, netMonthly: 0, aeRate: '0.262' };
	let waterfall = (data as any).waterfall ?? null;
	let incomeSources: any[] = (data as any).incomeSources ?? [];

	// ── Auto-save ───────────────────────────────────────────────────────────
	const DEBOUNCE_MS = 800;
	let saveIndicator: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
	let timers: Record<string, ReturnType<typeof setTimeout>> = {};

	async function autoSave(field: string, value: unknown) {
		saveIndicator = 'saving';
		try {
			const updated = await api.put('/profile', { [field]: value });
			profile = updated;
			saveIndicator = 'saved';
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[revenue] Save failed:', err);
			saveIndicator = 'error';
		}
	}

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

	// ── Income sources ──────────────────────────────────────────────────────
	let expandedSourceId: string | null = null;

	function toggleExpand(id: string) {
		expandedSourceId = expandedSourceId === id ? null : id;
	}

	const SOURCE_TYPES = [
		{ value: 'client', label: 'Client' },
		{ value: 'product', label: 'Produit' },
		{ value: 'dividends', label: 'Dividendes' },
		{ value: 'sale', label: 'Vente' },
		{ value: 'rental', label: 'Locatif' },
		{ value: 'salary', label: 'Salaire' },
		{ value: 'other', label: 'Autre' },
	];

	const FREQUENCIES = [
		{ value: 'monthly', label: 'Mensuel' },
		{ value: 'annual', label: 'Annuel' },
		{ value: 'one_time', label: 'Ponctuel' },
	];

	const CONFIDENCE_OPTIONS = [
		{ value: 'high', label: '🟢 Élevée' },
		{ value: 'medium', label: '🟡 Moyenne' },
		{ value: 'low', label: '🔴 Faible' },
	];

	const QUICK_PRESETS = [
		{ label: 'Client régulier', source_type: 'client', frequency: 'monthly', confidence: 'high', is_ae_revenue: true },
		{ label: 'Produit/SaaS', source_type: 'product', frequency: 'monthly', confidence: 'medium', is_ae_revenue: true },
		{ label: 'Mission ponctuelle', source_type: 'client', frequency: 'one_time', confidence: 'high', is_ae_revenue: true },
		{ label: 'Dividendes', source_type: 'dividends', frequency: 'annual', confidence: 'medium', is_ae_revenue: false },
		{ label: 'Vente d\'actif', source_type: 'sale', frequency: 'one_time', confidence: 'medium', is_ae_revenue: false },
		{ label: 'Salaire (conjoint)', source_type: 'salary', frequency: 'monthly', confidence: 'high', is_ae_revenue: false },
	];

	let showPresets = false;

	async function createSourceFromPreset(preset: typeof QUICK_PRESETS[number]) {
		saveIndicator = 'saving';
		try {
			const created = await api.post('/income-sources', {
				label: preset.label,
				source_type: preset.source_type,
				amount: '0',
				frequency: preset.frequency,
				confidence: preset.confidence,
				is_ae_revenue: preset.is_ae_revenue,
			});
			incomeSources = [...incomeSources, created];
			expandedSourceId = created.id;
			showPresets = false;
			saveIndicator = 'saved';
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[revenue] Create source failed:', err);
			saveIndicator = 'error';
		}
	}

	async function saveSource(id: string, updates: Record<string, unknown>) {
		saveIndicator = 'saving';
		try {
			const updated = await api.put(`/income-sources/${id}`, updates);
			const idx = incomeSources.findIndex((s: any) => s.id === id);
			if (idx !== -1) incomeSources[idx] = updated;
			saveIndicator = 'saved';
			reloadStats();
			setTimeout(() => { saveIndicator = 'idle'; }, 1500);
		} catch (err) {
			console.error('[revenue] Save source failed:', err);
			saveIndicator = 'error';
		}
	}

	let sourceTimers: Record<string, ReturnType<typeof setTimeout>> = {};
	function debouncedSaveSource(id: string, updates: Record<string, unknown>) {
		clearTimeout(sourceTimers[id]);
		saveIndicator = 'saving';
		sourceTimers[id] = setTimeout(() => saveSource(id, updates), DEBOUNCE_MS);
	}

	async function deleteSource(id: string) {
		if (!confirm('Supprimer cette source de revenu ?')) return;
		try {
			await api.delete(`/income-sources/${id}`);
			incomeSources = incomeSources.filter((s: any) => s.id !== id);
			reloadStats();
		} catch (err) {
			console.error('[revenue] Delete source failed:', err);
		}
	}

	async function reloadStats() {
		try {
			const newSources = await api.get<any[]>('/income-sources');
			const all = newSources?.items ?? newSources ?? [];
			incomeSources = all;
			// Recompute stats client-side for immediate feedback;
			// the next page.server.ts load will get the canonical values.
		} catch { /* ignore */ }
	}

	// ── Growth rate computation (MUST be above timeline — used by buildTimeline) ─
	$: effectiveRate = profile.growth_preset === 'custom'
		? Number(profile.growth_rate_custom) || 0.03
		: (growthPresets[profile.growth_preset]?.rate
			? parseFloat(growthPresets[profile.growth_preset].rate)
			: 0.03);

	// ── 10-year timeline ────────────────────────────────────────────────────
	$: currentYear = new Date().getFullYear();
	$: timeline = buildTimeline();

	function buildTimeline(): Array<{ year: number; segments: Array<{ label: string; amount: number; color: string }>; total: number }> {
		const result = [];
		// Build a per-source growth rate map: per-source annual_growth_rate takes
		// priority; AE sources with no per-source rate fall back to effectiveRate.
		const sourceGrowthRates = new Map<string, number>();
		for (const s of incomeSources) {
			const perSrc = parseFloat(s.annual_growth_rate);
			if (!isNaN(perSrc) && perSrc > 0) {
				sourceGrowthRates.set(s.id, perSrc);
			} else if (s.is_ae_revenue && effectiveRate > 0) {
				sourceGrowthRates.set(s.id, effectiveRate);
			} else {
				sourceGrowthRates.set(s.id, 0);
			}
		}

		for (let y = currentYear; y < currentYear + 10; y++) {
			const yearStart = new Date(y, 0, 1);
			const yearEnd = new Date(y, 11, 31);
			const yearIndex = y - currentYear;
			const segments = incomeSources
				.filter((s: any) => s.is_active !== false)
				.filter((s: any) => !s.start_date || new Date(s.start_date) <= yearEnd)
				.filter((s: any) => !s.end_date || new Date(s.end_date) >= yearStart)
				.filter((s: any) => s.frequency !== 'one_time')
				.map((s: any) => {
					const baseAmount = s.frequency === 'annual' ? (parseFloat(s.amount) || 0) / 12 : (parseFloat(s.amount) || 0);
					const growth = sourceGrowthRates.get(s.id) ?? 0;
					const grown = baseAmount * Math.pow(1 + growth, yearIndex);
					return {
						label: s.label || '—',
						amount: grown,
						color: s.earner === 'spouse' ? 'purple' : 'teal',
					};
				});
			const total = segments.reduce((s: number, x: any) => s + x.amount, 0);
			result.push({ year: y, segments, total });
		}
		return result;
	}

	$: maxMonthly = Math.max(1, ...timeline.map(t => t.total));

	// ── 5-year preview ──────────────────────────────────────────────────────
	$: fiveYearPreview = Array.from({ length: 5 }, (_, i) =>
		Math.round(stats.grossMonthly * Math.pow(1 + effectiveRate, i) * 100) / 100
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
	function fmtDec2(n: number): string {
		return n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '€';
	}
	function pctStr(rate: any): string {
		const r = typeof rate === 'string' ? parseFloat(rate) : rate;
		return (r * 100).toFixed(0) + '%';
	}

	function freqLabel(f: string): string {
		if (f === 'monthly') return '/mois';
		if (f === 'annual') return '/an';
		return '';
	}

	function confDot(confidence: string): string {
		if (confidence === 'high') return '🟢';
		if (confidence === 'medium') return '🟡';
		return '🔴';
	}

	function confColor(confidence: string): string {
		if (confidence === 'high') return 'text-emerald-400';
		if (confidence === 'medium') return 'text-amber-400';
		return 'text-rose-400';
	}

	function dateToYM(d: string | null | undefined): string {
		if (!d) return '';
		return d.substring(0, 7);
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

	// ── Active user AE sources count for stats note ─────────────────────────
	$: activeSources = incomeSources.filter((s: any) => s.is_active !== false && s.earner === 'user' && s.is_ae_revenue);
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

	<!-- Income Sources Management -->
	<Card title="Sources de revenus" icon="💰" accent="teal" dataCocoDesc="Gestion des sources de revenus : ajoutez, modifiez et suivez vos différentes sources de revenus (clients, produits, dividendes, etc.).">
		<p class="text-[11px] text-zinc-400 mb-3">
			Gérez vos différentes sources de revenus. Chaque source a son propre rythme, sa durée et son niveau de confiance.
		</p>

		<!-- Source list -->
		<div class="space-y-2 mb-4">
			{#each incomeSources as source (source.id)}
				{@const s = source}
				<div class="border border-zinc-700/30 rounded-lg overflow-hidden" data-coco-desc="Source de revenu {s.label} — {parseFloat(s.amount)}€{freqLabel(s.frequency)}">
					<!-- Collapsed row -->
					<button
						onclick={() => toggleExpand(s.id)}
						class="w-full flex items-center gap-2 p-2 bg-zinc-900/60 hover:bg-zinc-900/80 transition-colors text-left"
					>
						<span class="w-2 h-2 rounded-full flex-shrink-0 {s.earner === 'spouse' ? 'bg-purple-500' : 'bg-teal-500'}"></span>
						<span class="text-xs text-zinc-300 flex-1 truncate">{s.label || '—'}</span>
						<span class="text-xs font-mono text-teal-400 flex-shrink-0">
							{parseFloat(s.amount || '0').toLocaleString('fr-FR')}€
							{freqLabel(s.frequency)}
						</span>
						<span class="text-[9px] px-1.5 py-0.5 rounded-full flex-shrink-0 {confColor(s.confidence)}" title={s.confidence}>
							{confDot(s.confidence)}
						</span>
						{#if s.end_date}
							<span class="text-[10px] text-zinc-500 flex-shrink-0">→ {dateToYM(s.end_date)}</span>
						{/if}
						<span class="text-zinc-500 text-xs flex-shrink-0">{expandedSourceId === s.id ? '▲' : '▼'}</span>
					</button>

					<!-- Expanded edit form -->
					{#if expandedSourceId === s.id}
						<div class="p-3 border-t border-zinc-800/40 bg-zinc-950/30 space-y-3">
							<!-- Label -->
							<label class="flex flex-col gap-1">
								<span class="text-[10px] text-zinc-500 font-medium">Nom</span>
								<input type="text" value={s.label || ''}
									oninput={(e) => {
										const val = (e.target as HTMLInputElement).value;
										s.label = val;
										debouncedSaveSource(s.id, { label: val });
									}}
									class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full" />
							</label>

							<div class="grid grid-cols-2 gap-3">
								<!-- Source type -->
								<label class="flex flex-col gap-1">
									<span class="text-[10px] text-zinc-500 font-medium">Type</span>
									<select value={s.source_type || 'other'}
										onchange={(e) => {
											const val = (e.target as HTMLSelectElement).value;
											s.source_type = val;
											debouncedSaveSource(s.id, { source_type: val });
										}}
										class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full">
										{#each SOURCE_TYPES as t}
											<option value={t.value}>{t.label}</option>
										{/each}
									</select>
								</label>

								<!-- Frequency -->
								<label class="flex flex-col gap-1">
									<span class="text-[10px] text-zinc-500 font-medium">Fréquence</span>
									<select value={s.frequency || 'monthly'}
										onchange={(e) => {
											const val = (e.target as HTMLSelectElement).value;
											s.frequency = val;
											debouncedSaveSource(s.id, { frequency: val });
										}}
										class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full">
										{#each FREQUENCIES as f}
											<option value={f.value}>{f.label}</option>
										{/each}
									</select>
								</label>

								<!-- Amount -->
								<label class="flex flex-col gap-1">
									<span class="text-[10px] text-zinc-500 font-medium">Montant (€)</span>
									<input type="number" min="0" step="100" value={parseFloat(s.amount || '0')}
										oninput={(e) => {
											const val = parseFloat((e.target as HTMLInputElement).value);
											if (!isNaN(val) && val >= 0) {
												s.amount = val.toString();
												debouncedSaveSource(s.id, { amount: val.toString() });
											}
										}}
										class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full" />
								</label>

								<!-- Confidence -->
								<label class="flex flex-col gap-1">
									<span class="text-[10px] text-zinc-500 font-medium">Confiance</span>
									<select value={s.confidence || 'medium'}
										onchange={(e) => {
											const val = (e.target as HTMLSelectElement).value;
											s.confidence = val;
											debouncedSaveSource(s.id, { confidence: val });
										}}
										class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full">
										{#each CONFIDENCE_OPTIONS as c}
											<option value={c.value}>{c.label}</option>
										{/each}
									</select>
								</label>

								<!-- Start date -->
								<label class="flex flex-col gap-1">
									<span class="text-[10px] text-zinc-500 font-medium">Date de début</span>
									<input type="date" value={s.start_date ? s.start_date.substring(0, 10) : ''}
										oninput={(e) => {
											const val = (e.target as HTMLInputElement).value;
											s.start_date = val;
											debouncedSaveSource(s.id, { start_date: val });
										}}
										class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full" />
								</label>

								<!-- End date -->
								<label class="flex flex-col gap-1">
									<span class="text-[10px] text-zinc-500 font-medium">Date de fin</span>
									<input type="date" value={s.end_date ? s.end_date.substring(0, 10) : ''}
										oninput={(e) => {
											const val = (e.target as HTMLInputElement).value;
											s.end_date = val || null;
											debouncedSaveSource(s.id, { end_date: val || null });
										}}
										class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full" />
								</label>

								<!-- Annual growth rate -->
								<label class="flex flex-col gap-1">
									<span class="text-[10px] text-zinc-500 font-medium">Croissance annuelle (%)</span>
									<input type="number" min="0" max="50" step="0.5"
										value={s.annual_growth_rate ? parseFloat(s.annual_growth_rate) * 100 : ''}
										placeholder="Utiliser le preset global"
										oninput={(e) => {
											const val = parseFloat((e.target as HTMLInputElement).value) / 100;
											if (!isNaN(val) && val >= 0) {
												s.annual_growth_rate = val.toString();
												debouncedSaveSource(s.id, { annual_growth_rate: val.toString() });
											}
										}}
										class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full" />
								</label>

								<!-- Is AE revenue -->
								<label class="flex items-center gap-2 pt-4">
									<input type="checkbox" checked={s.is_ae_revenue === true}
										onchange={(e) => {
											const val = (e.target as HTMLInputElement).checked;
											s.is_ae_revenue = val;
											debouncedSaveSource(s.id, { is_ae_revenue: val });
										}}
										class="w-4 h-4 rounded border-zinc-600 bg-zinc-900 text-teal-500 focus:ring-teal-500/30" />
									<span class="text-[10px] text-zinc-400">Revenu AE (soumis aux cotisations)</span>
								</label>
							</div>

							<!-- Notes -->
							<label class="flex flex-col gap-1">
								<span class="text-[10px] text-zinc-500 font-medium">Notes</span>
								<input type="text" value={s.notes || ''} placeholder="ex: Client principal, contrat 3 ans..."
									oninput={(e) => {
										const val = (e.target as HTMLInputElement).value;
										s.notes = val;
										debouncedSaveSource(s.id, { notes: val });
									}}
									class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-teal-500/60 w-full" />
							</label>

							<!-- Delete -->
							<button onclick={() => deleteSource(s.id)}
								class="text-[10px] text-zinc-600 hover:text-rose-400 transition-colors">
								Supprimer cette source
							</button>
						</div>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Quick-add presets -->
		{#if showPresets}
			<div class="mb-3 p-3 rounded-lg bg-zinc-900/40 border border-teal-800/20">
				<p class="text-[10px] text-zinc-500 mb-2">Choisissez un type de source :</p>
				<div class="grid grid-cols-2 md:grid-cols-3 gap-2">
					{#each QUICK_PRESETS as preset}
						<button onclick={() => createSourceFromPreset(preset)}
							class="text-left p-2 rounded-lg border border-zinc-700/30 bg-zinc-900/50 hover:border-teal-600/40 hover:bg-teal-950/20 transition-all text-[10px]">
							<span class="block text-zinc-200 font-medium">{preset.label}</span>
							<span class="block text-zinc-500">{FREQUENCIES.find(f => f.value === preset.frequency)?.label}</span>
						</button>
					{/each}
				</div>
				<button onclick={() => { showPresets = false; }}
					class="text-[10px] text-zinc-500 hover:text-zinc-300 mt-2">
					Annuler
				</button>
			</div>
		{/if}

		<button onclick={() => { showPresets = !showPresets; }}
			class="w-full border border-dashed border-teal-700/40 rounded-lg py-2.5 text-xs text-teal-400 hover:text-teal-300 hover:border-teal-500/60 transition-colors">
			+ Ajouter une source
		</button>
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
		{#if stats.grossMonthly > 0}
			<div class="mt-4 p-3 rounded-lg bg-zinc-900/30 border border-zinc-800/30">
				<p class="text-[10px] text-zinc-500 mb-2">Projection sur 5 ans</p>
				<div class="flex gap-2">
					{#each fiveYearPreview as val, i}
						<div class="flex-1 text-center bg-zinc-800/40 rounded-lg py-2 px-1">
							<span class="block text-[9px] text-zinc-500">{currentYear}+{i}</span>
							<span class="block text-[11px] font-mono text-teal-300 font-semibold">{fmtDec(val)}</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</Card>

	<!-- 10-Year Revenue Timeline -->
	{#if incomeSources.length > 0}
		<Card title="Timeline des revenus" icon="📊" accent="sky" dataCocoDesc="Aperçu sur 10 ans de vos sources de revenus actives. Chaque barre montre la contribution mensuelle de chaque source. Teal = vous, Violet = conjoint.">
			<p class="text-[11px] text-zinc-400 mb-3">
				Contribution mensuelle de chaque source sur les 10 prochaines années. Les sources ponctuelles ne sont pas affichées.
			</p>
			<div class="space-y-1">
				{#each timeline as yearData}
					{@const y = yearData}
					<div class="flex items-center gap-2">
						<span class="text-[10px] text-zinc-500 w-10 font-mono flex-shrink-0">{y.year}</span>
						<div class="flex-1 flex h-4 rounded overflow-hidden bg-zinc-800">
							{#if y.segments.length > 0}
								{#each y.segments as seg}
									<div
										class="h-full {seg.color === 'teal' ? 'bg-teal-600/60' : 'bg-purple-600/60'}"
										style="width: {Math.max(0.5, (seg.amount / maxMonthly) * 100)}%"
										title="{seg.label}: {Math.round(seg.amount).toLocaleString('fr-FR')}€/mois"
									></div>
								{/each}
							{:else}
								<div class="h-full w-full bg-zinc-800/50"></div>
							{/if}
						</div>
						<span class="text-[10px] font-mono text-zinc-400 w-16 text-right flex-shrink-0">
							{Math.round(y.total).toLocaleString('fr-FR')}€
						</span>
					</div>
				{/each}
			</div>
			<!-- Legend -->
			<div class="flex items-center gap-4 mt-3 pt-2 border-t border-zinc-800/30">
				<div class="flex items-center gap-1.5">
					<span class="w-3 h-3 rounded bg-teal-600/60 inline-block"></span>
					<span class="text-[10px] text-zinc-500">Vous</span>
				</div>
				<div class="flex items-center gap-1.5">
					<span class="w-3 h-3 rounded bg-purple-600/60 inline-block"></span>
					<span class="text-[10px] text-zinc-500">Conjoint</span>
				</div>
			</div>
		</Card>
	{/if}

	<!-- Tax breaks (unchanged) -->
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

	<!-- Sprint 6: Disposable Income Waterfall (TASK-6.8) -->
	{#if waterfall}
		<Card title="Où va votre argent ?" icon="🌊" accent="teal" dataCocoDesc="Cascade du revenu disponible : du CA brut à l'épargne réelle. Chaque barre montre une étape du flux d'argent mensuel.">
			<p class="text-[11px] text-zinc-400 mb-3">Flux mensuel — {waterfall.year} (à {waterfall.age} ans)</p>

			<div class="space-y-1.5">
				<!-- Gross CA -->
				<div class="flex items-center gap-2">
					<span class="text-[10px] text-zinc-400 w-28 text-right">CA brut</span>
					<div class="flex-1 h-5 bg-zinc-800 rounded overflow-hidden">
						<div class="h-full bg-teal-500/60 rounded" style="width: 100%"></div>
					</div>
					<span class="text-[11px] font-mono text-teal-300 w-24 text-right">{fmtDec(parseFloat(waterfall.monthly.gross_ca))}</span>
				</div>

				<!-- Charges -->
				<div class="flex items-center gap-2">
					<span class="text-[10px] text-zinc-400 w-28 text-right">Cotisations</span>
					<div class="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
						<div class="h-full bg-rose-500/40 rounded ml-auto" style="width: {Math.min(100, (parseFloat(waterfall.monthly.charges) / Math.max(1, parseFloat(waterfall.monthly.gross_ca))) * 100)}%"></div>
					</div>
					<span class="text-[11px] font-mono text-rose-400 w-24 text-right">-{fmtDec(parseFloat(waterfall.monthly.charges))}</span>
				</div>

				<!-- Net after charges -->
				<div class="flex items-center gap-2 py-1 border-t border-zinc-800/50">
					<span class="text-[10px] text-zinc-300 w-28 text-right font-medium">Net après cotis.</span>
					<div class="flex-1 h-1 bg-teal-500/20 rounded-full"></div>
					<span class="text-[11px] font-mono font-bold text-teal-300 w-24 text-right">{fmtDec(parseFloat(waterfall.monthly.net_after_charges))}</span>
				</div>

				<!-- Autres revenus (conjoint, non-AE) -->
				{#if parseFloat(waterfall.monthly.autres_revenus) > 0}
					<div class="flex items-center gap-2">
						<span class="text-[10px] text-zinc-400 w-28 text-right">Autres revenus</span>
						<div class="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
							<div class="h-full bg-teal-500/40 rounded" style="width: {Math.min(100, (parseFloat(waterfall.monthly.autres_revenus) / Math.max(1, parseFloat(waterfall.monthly.gross_ca))) * 100)}%"></div>
						</div>
						<span class="text-[11px] font-mono text-teal-300 w-24 text-right">+{fmtDec(parseFloat(waterfall.monthly.autres_revenus))}</span>
					</div>
				{/if}

				<!-- Spouse charges (cotisations conjoint) -->
				{#if parseFloat(waterfall.monthly.spouse_charges) > 0}
					<div class="flex items-center gap-2">
						<span class="text-[10px] text-zinc-400 w-28 text-right">Cotisations conjoint</span>
						<div class="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
							<div class="h-full bg-rose-400/30 rounded ml-auto" style="width: {Math.min(100, (parseFloat(waterfall.monthly.spouse_charges) / Math.max(1, parseFloat(waterfall.monthly.gross_ca))) * 100)}%"></div>
						</div>
						<span class="text-[11px] font-mono text-rose-400 w-24 text-right">-{fmtDec(parseFloat(waterfall.monthly.spouse_charges))}</span>
					</div>
				{/if}

				<!-- Base expenses -->
				<div class="flex items-center gap-2">
					<span class="text-[10px] text-zinc-400 w-28 text-right">Dépenses base</span>
					<div class="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
						<div class="h-full bg-amber-500/40 rounded ml-auto" style="width: {Math.min(100, (parseFloat(waterfall.monthly.base_expenses) / Math.max(1, parseFloat(waterfall.monthly.gross_ca))) * 100)}%"></div>
					</div>
					<span class="text-[11px] font-mono text-amber-400 w-24 text-right">-{fmtDec(parseFloat(waterfall.monthly.base_expenses))}</span>
				</div>

				<!-- Loans -->
				{#if parseFloat(waterfall.monthly.loan_payments) > 0}
					<div class="flex items-center gap-2">
						<span class="text-[10px] text-zinc-400 w-28 text-right">Crédits</span>
						<div class="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
							<div class="h-full bg-purple-500/40 rounded ml-auto" style="width: {Math.min(100, (parseFloat(waterfall.monthly.loan_payments) / Math.max(1, parseFloat(waterfall.monthly.gross_ca))) * 100)}%"></div>
						</div>
						<span class="text-[11px] font-mono text-purple-400 w-24 text-right">-{fmtDec(parseFloat(waterfall.monthly.loan_payments))}</span>
					</div>
				{/if}

				<!-- Life costs summary -->
				{#if parseFloat(waterfall.monthly.kid_costs) + parseFloat(waterfall.monthly.pet_costs) + parseFloat(waterfall.monthly.car_costs) + parseFloat(waterfall.monthly.tech_costs) + parseFloat(waterfall.monthly.recurring_costs) > 0}
					{@const lifeTotal = parseFloat(waterfall.monthly.kid_costs) + parseFloat(waterfall.monthly.pet_costs) + parseFloat(waterfall.monthly.car_costs) + parseFloat(waterfall.monthly.tech_costs) + parseFloat(waterfall.monthly.recurring_costs)}
					<div class="flex items-center gap-2">
						<span class="text-[10px] text-zinc-400 w-28 text-right">Vie (enfants, etc.)</span>
						<div class="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
							<div class="h-full bg-rose-400/30 rounded ml-auto" style="width: {Math.min(100, (lifeTotal / Math.max(1, parseFloat(waterfall.monthly.gross_ca))) * 100)}%"></div>
						</div>
						<span class="text-[11px] font-mono text-rose-400 w-24 text-right">-{fmtDec(lifeTotal)}</span>
					</div>
				{/if}

				<!-- CAF / Tax credits -->
				{#if parseFloat(waterfall.monthly.caf_income) > 0 || parseFloat(waterfall.monthly.tax_credits) > 0}
					<div class="flex items-center gap-2">
						<span class="text-[10px] text-zinc-400 w-28 text-right">Aides & crédits</span>
						<div class="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
							<div class="h-full bg-emerald-500/40 rounded" style="width: {Math.min(100, ((parseFloat(waterfall.monthly.caf_income) + parseFloat(waterfall.monthly.tax_credits)) / Math.max(1, parseFloat(waterfall.monthly.gross_ca))) * 100)}%"></div>
						</div>
						<span class="text-[11px] font-mono text-emerald-400 w-24 text-right">+{fmtDec(parseFloat(waterfall.monthly.caf_income) + parseFloat(waterfall.monthly.tax_credits))}</span>
					</div>
				{/if}

				<!-- Disposable -->
				<div class="flex items-center gap-2 py-1 border-t border-zinc-800/50">
					<span class="text-[10px] text-zinc-300 w-28 text-right font-medium">Revenu disponible</span>
					<div class="flex-1 h-1 bg-teal-500/20 rounded-full"></div>
					<span class="text-[11px] font-mono font-bold {parseFloat(waterfall.monthly.disposable) >= 0 ? 'text-teal-300' : 'text-rose-400'} w-24 text-right">{parseFloat(waterfall.monthly.disposable) >= 0 ? '' : '-'}{fmtDec(Math.abs(parseFloat(waterfall.monthly.disposable)))}</span>
				</div>

				<!-- Savings -->
				<div class="flex items-center gap-2">
					<span class="text-[10px] text-zinc-400 w-28 text-right">Épargne prévue</span>
					<div class="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
						<div class="h-full bg-sky-500/40 rounded ml-auto" style="width: {Math.min(100, (parseFloat(waterfall.monthly.savings_planned) / Math.max(1, parseFloat(waterfall.monthly.gross_ca))) * 100)}%"></div>
					</div>
					<span class="text-[11px] font-mono text-sky-400 w-24 text-right">-{fmtDec(parseFloat(waterfall.monthly.savings_planned))}</span>
				</div>

				<!-- Surplus / Deficit -->
				<div class="flex items-center gap-2 p-2 rounded-lg {waterfall.status === 'surplus' ? 'bg-emerald-950/20 border border-emerald-800/20' : waterfall.status === 'deficit' ? 'bg-rose-950/20 border border-rose-800/20' : 'bg-zinc-900/40 border border-zinc-800/20'}">
					<span class="text-[10px] font-semibold w-28 text-right {waterfall.status === 'surplus' ? 'text-emerald-300' : waterfall.status === 'deficit' ? 'text-rose-300' : 'text-zinc-300'}">
						{waterfall.status === 'surplus' ? 'Excédent' : waterfall.status === 'deficit' ? 'Déficit' : 'Équilibre'}
					</span>
					<div class="flex-1 h-1 rounded-full {waterfall.status === 'surplus' ? 'bg-emerald-500/30' : waterfall.status === 'deficit' ? 'bg-rose-500/30' : 'bg-zinc-700'}"></div>
					<span class="text-[11px] font-mono font-bold {waterfall.status === 'surplus' ? 'text-emerald-400' : waterfall.status === 'deficit' ? 'text-rose-400' : 'text-zinc-300'} w-24 text-right">
						{parseFloat(waterfall.monthly.monthly_surplus_deficit) >= 0 ? '+' : ''}{fmtDec(parseFloat(waterfall.monthly.monthly_surplus_deficit))}
					</span>
				</div>
			</div>

			{#if waterfall.deficit_note}
				<p class="text-[10px] text-rose-400/70 mt-3 leading-relaxed">{waterfall.deficit_note}</p>
			{/if}
		</Card>
	{/if}
</div>