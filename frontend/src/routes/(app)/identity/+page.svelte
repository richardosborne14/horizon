<script lang="ts">
	/**
	 * Identity page — user financial profile setup.
	 *
	 * Sprint 6 (TASK-6.1): Career history CRUD.
	 * Sprint 7 (TASK-7.9): Spouse card, CC options, spouse career timeline, tax parts prompt.
	 * All fields auto-save after 800ms debounce via PUT /api/profile.
	 */
	import { api } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import type { PageData } from './$types';

	export let data: PageData;

	// ── Local state synced from server data ──────────────────────────────────
	let profile = data.profile ?? {};
	let rateSchedule = data.rateSchedule ?? [];
	let allSchedules = data.allSchedules ?? [];
	let careerPeriods: any[] = (data as any).careerPeriods ?? [];
	let careerSummary: any = (data as any).careerSummary ?? null;
	let netWorth: any = (data as any).netWorth ?? null;
	let projectedProperty = 0;
	let freedCapitalEstimate = 0;

	// Spouse state (TASK-7.9)
	let spouse: any = (data as any).spouse ?? null;
	let spouseCareer: any[] = (data as any).spouseCareer ?? [];
	let spouseCareerSummary: any = (data as any).spouseCareerSummary ?? null;
	let ccEstimate: any = (data as any).ccEstimate ?? null;

	// CC labels
	const ccLabels: Record<string, string> = {
		tiers_plafond: '1/3 du plafond SS',
		moitie_plafond: '1/2 du plafond SS',
		tiers_revenu: '1/3 du revenu',
		moitie_revenu: '1/2 du revenu',
	};

	// CC availability: EIRL/EURL + married/PACSed
	$: canBeCC = ['eirl', 'eurl'].includes(profile.status ?? '') &&
		spouse &&
		['married', 'pacsed'].includes(spouse.relationship_type);

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

	const spouseStatusOptions = [
		{ value: 'cdi', label: 'CDI' },
		{ value: 'cdd', label: 'CDD' },
		{ value: 'ae', label: 'Auto-entrepreneur' },
		{ value: 'retired', label: 'Retraité(e)' },
		{ value: 'inactive', label: 'Inactif/ive' },
		{ value: 'conjointe_collaboratrice', label: 'Conjoint(e) collaborateur/trice' },
	];

	const relationshipOptions = [
		{ value: 'married', label: 'Marié(e)' },
		{ value: 'pacsed', label: 'PACSé(e)' },
		{ value: 'concubinage', label: 'Concubinage' },
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

	let debounceTimers: Record<string, ReturnType<typeof setTimeout>> = {};

	function debouncedSave(field: string, value: unknown) {
		clearTimeout(debounceTimers[field]);
		saveIndicator = 'saving';
		debounceTimers[field] = setTimeout(() => autoSave(field, value), DEBOUNCE_MS);
	}

	async function immediateSave(field: string, value: unknown) {
		clearTimeout(debounceTimers[field]);
		await autoSave(field, value);
	}

	async function onAeTypeChange(newType: string) {
		profile.ae_activity_type = newType;
		await autoSave('ae_activity_type', newType);
		try {
			const resp = await api.get<{ schedule: Array<{ from_year: number; rate: string }> }>(
				'/rates/ae-schedule', { type: newType }
			);
			rateSchedule = resp.schedule;
		} catch (err) {
			console.error('[identity] Failed to fetch rate schedule:', err);
		}
	}

	// ── Spouse CRUD (TASK-7.9) ─────────────────────────────────────────────
	async function createSpouse() {
		try {
			const created = await api.post('/spouse', {
				relationship_type: 'married',
				status: 'cdi',
			});
			spouse = created;
			// Re-fetch CC estimate if applicable
			await refreshCcEstimate();
		} catch (err) {
			console.error('[identity] Spouse create failed:', err);
		}
	}

	async function debouncedSaveSpouse() {
		if (!spouse) return;
		saveIndicator = 'saving';
		try {
			const updated = await api.put('/spouse', {
				first_name: spouse.first_name,
				birth_date: spouse.birth_date,
				relationship_type: spouse.relationship_type,
				status: spouse.status,
				is_conjointe_collaboratrice: spouse.is_conjointe_collaboratrice,
				cc_cotisation_option: spouse.cc_cotisation_option,
				monthly_gross_income: spouse.monthly_gross_income,
			});
			spouse = updated;
			saveIndicator = 'saved';
			triggerSaveIndicator();
			await refreshCcEstimate();
		} catch (err) {
			console.error('[identity] Spouse save failed:', err);
			saveIndicator = 'error';
		}
	}

	async function confirmDeleteSpouse() {
		if (!spouse) return;
		if (!confirm(`Retirer ${spouse.first_name || 'le conjoint'} de votre profil ?`)) return;
		try {
			await api.delete('/spouse');
			spouse = null;
			spouseCareer = [];
			spouseCareerSummary = null;
			ccEstimate = null;
		} catch (err) {
			console.error('[identity] Spouse delete failed:', err);
		}
	}

	async function ccOptionChange(option: string) {
		if (!spouse) return;
		spouse.cc_cotisation_option = option;
		await debouncedSaveSpouse();
	}

	async function refreshCcEstimate() {
		if (!spouse?.is_conjointe_collaboratrice) return;
		try {
			const estimate = await api.get('/spouse/cc-estimate');
			ccEstimate = estimate;
		} catch (err) {
			console.error('[identity] CC estimate fetch failed:', err);
		}
	}

	async function updateTaxParts(newParts: number) {
		await immediateSave('tax_parts', newParts);
	}

	// ── Net Worth / Property (TASK-7.16) ──────────────────────────────────
	let netWorthSaveTimer: ReturnType<typeof setTimeout>;

	async function saveNetWorth() {
		if (!netWorth) return;
		saveIndicator = 'saving';
		clearTimeout(netWorthSaveTimer);
		netWorthSaveTimer = setTimeout(async () => {
			try {
				const payload: any = {
					cash_current_accounts: netWorth.cash_current_accounts ?? 0,
					cash_savings_other: netWorth.cash_savings_other ?? 0,
					property_primary_value: netWorth.property_primary_value ?? 0,
					property_other_value: netWorth.property_other_value ?? 0,
					property_appreciation_rate: netWorth.property_appreciation_rate ?? 0.02,
					downsize_enabled: netWorth.downsize_enabled ?? false,
					downsize_year: netWorth.downsize_enabled ? (netWorth.downsize_year || null) : null,
					downsize_target_value: netWorth.downsize_enabled ? (netWorth.downsize_target_value || null) : null,
					business_value: netWorth.business_value ?? 0,
					vehicle_value: netWorth.vehicle_value ?? 0,
					other_assets: netWorth.other_assets ?? 0,
					other_assets_label: netWorth.other_assets_label ?? null,
					other_debts: netWorth.other_debts ?? 0,
					other_debts_label: netWorth.other_debts_label ?? null,
					snapshot_date: new Date().toISOString().substring(0, 10),
				};
				const updated = await api.put('/net-worth', payload);
				netWorth = updated;
				saveIndicator = 'saved';
				triggerSaveIndicator();
			} catch (err) {
				console.error('[identity] Net worth save failed:', err);
				saveIndicator = 'error';
			}
		}, DEBOUNCE_MS);
	}

	$: if (netWorth) {
		const baseVal = parseFloat(netWorth.property_primary_value ?? 0);
		const appreciation = parseFloat(netWorth.property_appreciation_rate ?? 0.02);
		const targetAge = parseInt(profile.target_retirement_age ?? '67');
		const currentAge = parseInt(profile.current_age ?? '0');
		const yearsToRetirement = Math.max(0, targetAge - currentAge);
		projectedProperty = baseVal * Math.pow(1 + appreciation, yearsToRetirement);
		freedCapitalEstimate = 0;
		if (netWorth.downsize_enabled && netWorth.downsize_target_value) {
			const downsizeYear = netWorth.downsize_year || (new Date().getFullYear() + yearsToRetirement);
			const yearsToDownsize = Math.max(0, downsizeYear - new Date().getFullYear());
			const propAtDownsize = baseVal * Math.pow(1 + appreciation, yearsToDownsize);
			const netSale = propAtDownsize * 0.92;
			const grossPurchase = parseFloat(netWorth.downsize_target_value) * 1.08;
			freedCapitalEstimate = Math.max(0, netSale - grossPurchase);
		}
	}

	// ── Career CRUD (TASK-6.1) ─────────────────────────────────────────────
	let showCareerForm = false;
	let newCareerType = 'cdi';
	let newCareerStart = '';
	let newCareerEnd = '';
	let newCareerEmployer = '';
	let newCareerTitle = '';
	let newCareerSalary = 0;
	let newCareerFullTime = true;
	let newCareerTimePct = 100;

	$: salaryLabel = {
		cdi: 'Salaire brut annuel',
		cdd: 'Salaire brut annuel',
		interim: 'Salaire brut annuel',
		ae: 'CA brut annuel',
		sasu: 'Rémunération brute annuelle',
		unemployment: 'ARE brute annuelle',
		parental_leave: 'Indemnités brutes annuelles',
		education: 'Revenu brut annuel',
		other: 'Revenu brut annuel',
	}[newCareerType] || 'Revenu brut annuel';

	const careerTypeOptions = [
		{ value: 'cdi', label: 'CDI' },
		{ value: 'cdd', label: 'CDD' },
		{ value: 'interim', label: 'Intérim' },
		{ value: 'ae', label: 'Auto-entrepreneur' },
		{ value: 'sasu', label: 'SASU (président salarié)' },
		{ value: 'unemployment', label: 'Chômage (ARE)' },
		{ value: 'parental_leave', label: 'Congé parental' },
		{ value: 'education', label: 'Études' },
		{ value: 'other', label: 'Autre' },
	];

	const careerColorMap: Record<string, string> = {
		cdi: 'teal', cdd: 'emerald', interim: 'purple', ae: 'emerald',
		sasu: 'sky', unemployment: 'amber', parental_leave: 'rose',
		education: 'zinc', other: 'zinc',
	};

	async function addCareerPeriod() {
		if (!newCareerStart) return;
		const payload: Record<string, any> = {
			period_type: newCareerType,
			start_date: newCareerStart,
			is_full_time: newCareerFullTime,
			time_percentage: newCareerTimePct,
		};
		if (newCareerEnd) payload.end_date = newCareerEnd;
		if (newCareerEmployer) payload.employer_name = newCareerEmployer;
		if (newCareerTitle) payload.job_title = newCareerTitle;
		if (newCareerSalary > 0) payload.annual_gross = newCareerSalary;

		try {
			const period = await api.post('/career', payload);
			if (period) {
				careerPeriods = [...careerPeriods, period];
				const summary = await api.get('/career/summary?owner=user');
				if (summary) careerSummary = summary;
			}
			newCareerStart = '';
			newCareerEnd = '';
			newCareerEmployer = '';
			newCareerTitle = '';
			newCareerSalary = 0;
			showCareerForm = false;
		} catch (err) {
			console.error('[identity] Career create failed:', err);
		}
	}

	async function deleteCareerPeriod(id: string) {
		try {
			await api.delete(`/career/${id}`);
			careerPeriods = careerPeriods.filter((p: any) => p.id !== id);
			const summary = await api.get('/career/summary?owner=user');
			if (summary) careerSummary = summary;
		} catch (err) {
			console.error('[identity] Career delete failed:', err);
		}
	}

	// Spouse career CRUD
	let showSpouseCareerForm = false;
	let newSpCareerType = 'cdi';
	let newSpCareerStart = '';
	let newSpCareerEnd = '';
	let newSpCareerEmployer = '';
	let newSpCareerTitle = '';
	let newSpCareerSalary = 0;
	let newSpCareerFullTime = true;
	let newSpCareerTimePct = 100;

	$: spSalaryLabel = {
		cdi: 'Salaire brut annuel',
		cdd: 'Salaire brut annuel',
		interim: 'Salaire brut annuel',
		ae: 'CA brut annuel',
		sasu: 'Rémunération brute annuelle',
		unemployment: 'ARE brute annuelle',
		parental_leave: 'Indemnités brutes annuelles',
		education: 'Revenu brut annuel',
		other: 'Revenu brut annuel',
	}[newSpCareerType] || 'Revenu brut annuel';

	async function addSpouseCareerPeriod() {
		if (!newSpCareerStart) return;
		const payload: Record<string, any> = {
			period_type: newSpCareerType,
			start_date: newSpCareerStart,
			is_full_time: newSpCareerFullTime,
			time_percentage: newSpCareerTimePct,
			owner: 'spouse',
		};
		if (newSpCareerEnd) payload.end_date = newSpCareerEnd;
		if (newSpCareerEmployer) payload.employer_name = newSpCareerEmployer;
		if (newSpCareerTitle) payload.job_title = newSpCareerTitle;
		if (newSpCareerSalary > 0) payload.annual_gross = newSpCareerSalary;

		try {
			const period = await api.post('/career', payload);
			if (period) {
				spouseCareer = [...spouseCareer, period];
				const summary = await api.get('/career/summary?owner=spouse');
				if (summary) spouseCareerSummary = summary;
			}
			newSpCareerStart = '';
			newSpCareerEnd = '';
			newSpCareerEmployer = '';
			newSpCareerTitle = '';
			newSpCareerSalary = 0;
			showSpouseCareerForm = false;
		} catch (err) {
			console.error('[identity] Spouse career create failed:', err);
		}
	}

	async function deleteSpouseCareerPeriod(id: string) {
		try {
			await api.delete(`/career/${id}`);
			spouseCareer = spouseCareer.filter((p: any) => p.id !== id);
			const summary = await api.get('/career/summary?owner=spouse');
			if (summary) spouseCareerSummary = summary;
		} catch (err) {
			console.error('[identity] Spouse career delete failed:', err);
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

		<!-- Tax parts prompt when spouse is married/PACSed and parts < 2 -->
		{#if spouse && ['married', 'pacsed'].includes(spouse.relationship_type) && (profile.tax_parts ?? 1) < 2}
			<div class="bg-amber-950/20 border border-amber-800/30 rounded-lg p-3 mt-3">
				<p class="text-xs text-amber-300">
					Vos parts fiscales sont à {profile.tax_parts ?? '1'}. Pour un couple {spouse.relationship_type === 'married' ? 'marié' : 'PACSé'}, c'est généralement 2.0 (+0.5/enfant, +1 au 3ème).
					<button onclick={() => updateTaxParts(2)} class="text-amber-200 underline ml-1">Mettre à jour →</button>
				</p>
			</div>
		{/if}
	</Card>

	<!-- Card 2: Statut & Activité -->
	<Card title="Statut & Activité" icon="⚖️" accent="amber" dataCocoDesc="Statut juridique, type d'activité AE, versement libératoire et historique des taux de cotisation">
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
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
			</div>
		{/if}
	</Card>

	<!-- Card 3: Conjoint(e) (TASK-7.9) -->
	<Card title={`Conjoint(e)${spouse?.first_name ? ' — ' + spouse.first_name : ''}`} icon="💑" accent="purple" dataCocoDesc="Informations sur le conjoint : identité, statut professionnel, option conjointe collaboratrice">
		{#if !spouse}
			<p class="text-xs text-zinc-500 mb-3">Ajoutez votre conjoint(e) pour une projection du foyer.</p>
			<button
				onclick={createSpouse}
				class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-purple-700/50"
				data-coco-desc="Créer une fiche conjoint"
			>
				+ Ajouter un conjoint
			</button>
		{:else}
			<div class="grid grid-cols-2 gap-3">
				<label class="flex flex-col gap-1">
					<span class="text-[10px] text-zinc-500">Prénom</span>
					<input
						type="text"
						value={spouse.first_name ?? ''}
						oninput={(e) => { spouse.first_name = (e.target as HTMLInputElement).value; }}
						onchange={debouncedSaveSpouse}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 w-full"
						data-coco-desc="Prénom du conjoint"
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-[10px] text-zinc-500">Date de naissance</span>
					<input
						type="date"
						value={formatDateValue(spouse.birth_date)}
						onchange={(e) => { spouse.birth_date = (e.target as HTMLInputElement).value || null; debouncedSaveSpouse(); }}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 w-full"
						data-coco-desc="Date de naissance du conjoint"
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-[10px] text-zinc-500">Relation</span>
					<select
						value={spouse.relationship_type ?? 'married'}
						onchange={(e) => { spouse.relationship_type = (e.target as HTMLSelectElement).value; debouncedSaveSpouse(); }}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 w-full"
						data-coco-desc="Type de relation avec le conjoint"
					>
						{#each relationshipOptions as opt}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-[10px] text-zinc-500">Statut pro.</span>
					<select
						value={spouse.status ?? 'cdi'}
						onchange={(e) => { spouse.status = (e.target as HTMLSelectElement).value; debouncedSaveSpouse(); }}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 w-full"
						data-coco-desc="Statut professionnel du conjoint"
					>
						{#each spouseStatusOptions as opt}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>
				</label>
			</div>

			<!-- Monthly income -->
			<label class="flex flex-col gap-1 mt-3">
				<span class="text-[10px] text-zinc-500">Revenu brut mensuel (€)</span>
				<input
					type="number"
					min="0"
					step="100"
					value={spouse.monthly_gross_income ?? ''}
					oninput={(e) => { spouse.monthly_gross_income = parseFloat((e.target as HTMLInputElement).value) || null; }}
					onchange={debouncedSaveSpouse}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 w-40"
					data-coco-desc="Revenu brut mensuel du conjoint"
				/>
			</label>

			<!-- CC section -->
			{#if canBeCC}
				<div class="mt-3 p-3 bg-purple-950/20 border border-purple-800/20 rounded-lg">
					<label class="flex items-center gap-2 text-xs text-zinc-300 mb-2 cursor-pointer">
						<input
							type="checkbox"
							checked={spouse.is_conjointe_collaboratrice ?? false}
							onchange={(e) => { spouse.is_conjointe_collaboratrice = (e.target as HTMLInputElement).checked; debouncedSaveSpouse(); }}
							data-coco-desc="Activer le statut conjoint collaborateur"
						/>
						Conjoint(e) collaborateur/trice
					</label>
					{#if spouse.is_conjointe_collaboratrice && ccEstimate}
						<div class="grid grid-cols-2 gap-2 mt-2">
							{#each Object.entries(ccEstimate) as [option, data]}
								<button
									class="p-2 rounded-lg text-left border text-xs transition-colors {spouse.cc_cotisation_option === option ? 'border-purple-500 bg-purple-900/30' : 'border-zinc-700/30 hover:border-purple-700/30'}"
									onclick={() => ccOptionChange(option)}
									data-coco-desc={`Option CC : ${ccLabels[option] || option}, cotisation ${(data as any).cotisation_mensuelle || 'N/A'}€/mois`}
								>
									<p class="text-zinc-300 font-medium">{ccLabels[option] || option}</p>
									<p class="text-purple-400 font-mono">{(data as any).cotisation_mensuelle || '—'}€/mois</p>
								</button>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			<button
				onclick={confirmDeleteSpouse}
				class="text-xs text-zinc-600 hover:text-rose-400 mt-3"
				data-coco-desc="Retirer le conjoint du profil"
			>
				Retirer le conjoint
			</button>
		{/if}
	</Card>

	<!-- Card 4: Parcours professionnel -->
	<Card title="Parcours professionnel" icon="📋" accent="teal" dataCocoDesc="Historique d'emploi pour le calcul de la retraite">
		<p class="text-[11px] text-zinc-400 mb-3">Votre historique alimente le calcul de votre retraite. Chaque période validée compte.</p>

		{#if careerSummary}
			<div class="bg-teal-950/20 border border-teal-800/20 rounded-lg p-3 mb-3">
				<div class="flex items-center gap-4 flex-wrap">
					<div class="text-center">
						<span class="block text-lg font-bold font-mono text-teal-300">{careerSummary.total_trimestres_estimated ?? 0}</span>
						<span class="text-[10px] text-zinc-500">trimestres validés</span>
					</div>
					<div class="text-center">
						<span class="block text-lg font-bold font-mono text-zinc-400">{careerSummary.trimestres_required ?? 172}</span>
						<span class="text-[10px] text-zinc-500">requis</span>
					</div>
					<div class="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden min-w-[100px]">
						<div
							class="h-full bg-teal-500 rounded-full transition-all duration-500"
							style="width: {Math.min(100, ((careerSummary.total_trimestres_estimated ?? 0) / (careerSummary.trimestres_required || 1)) * 100)}%"
						></div>
					</div>
				</div>
				{#if careerSummary.current_period}
					<p class="text-[10px] text-zinc-500 mt-2">
						Situation actuelle : <strong class="text-zinc-300">{careerSummary.current_period.type?.toUpperCase()}</strong> depuis {careerSummary.current_period.since?.substring(0, 4)}
					</p>
				{/if}
			</div>
		{/if}

		{#if careerPeriods.length > 0}
			<div class="space-y-2 mb-3">
				{#each careerPeriods as period (period.id)}
					<div class="flex items-center gap-2 p-2 bg-zinc-900/60 border border-zinc-700/30 rounded-lg" data-coco-desc={`Période ${period.period_type} ${period.employer_name || ''} ${period.start_date?.substring(0, 4) || ''}-${period.end_date?.substring(0, 4) || 'actuel'}`}>
						<span class="w-2 h-2 rounded-full flex-shrink-0 bg-{careerColorMap[period.period_type] || 'zinc'}-500"></span>
						<span class="text-xs text-zinc-300 flex-1">
							{period.period_type?.toUpperCase()}
							{#if period.employer_name} — {period.employer_name}{/if}
							{#if period.job_title} ({period.job_title}){/if}
						</span>
						<span class="text-[10px] text-zinc-500">
							{period.start_date?.substring(0, 4) || '?'}–{period.end_date?.substring(0, 4) || 'actuel'}
						</span>
						<span class="text-[10px] text-zinc-500 font-mono">
							{#if period.annual_gross}{parseFloat(period.annual_gross).toLocaleString('fr-FR')}€ brut/an{/if}
						</span>
						<span class="text-[10px] text-zinc-600 bg-zinc-800/40 px-1 py-0.5 rounded">{period.trimestres_estimated ?? 0} trim.</span>
						<button
							class="text-zinc-600 hover:text-rose-400 text-xs"
							onclick={() => deleteCareerPeriod(period.id)}
							data-coco-desc={`Supprimer la période ${period.period_type} ${period.start_date?.substring(0, 4)}`}
						>✕</button>
					</div>
				{/each}
			</div>
		{:else}
			<p class="text-xs text-zinc-500 italic mb-2">Aucune période enregistrée.</p>
		{/if}

		{#if showCareerForm}
			<div class="flex flex-wrap items-end gap-2 mt-3 p-3 bg-zinc-900/40 border border-zinc-700/30 rounded-lg">
				<select bind:value={newCareerType} class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200">
					{#each careerTypeOptions as opt}
						<option value={opt.value}>{opt.label}</option>
					{/each}
				</select>
				<input type="date" bind:value={newCareerStart} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
				<input type="date" bind:value={newCareerEnd} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
				<input type="text" bind:value={newCareerEmployer} placeholder="Employeur" class="w-28 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
				<input type="number" bind:value={newCareerSalary} min="0" step="1000" placeholder={salaryLabel} class="w-28 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
				<button class="bg-teal-600 text-white text-xs rounded px-3 py-1 hover:bg-teal-500" onclick={addCareerPeriod}>Ajouter</button>
				<button class="text-zinc-500 text-xs" onclick={() => showCareerForm = false}>Annuler</button>
			</div>
		{:else}
			<button
				class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-teal-700/50 transition-colors mt-2"
				onclick={() => showCareerForm = true}
				data-coco-desc="Ouvrir le formulaire d'ajout de période professionnelle"
			>
				+ Ajouter une période
			</button>
		{/if}
	</Card>

	<!-- Card 5: Résidence principale (TASK-7.16) -->
	<Card title="Résidence principale" icon="🏠" accent="emerald" dataCocoDesc="Valeur estimée de votre résidence principale, appréciation annuelle et simulation de downsizing">
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Valeur estimée</span>
				<input
					type="number"
					min="0"
					step="10000"
					value={netWorth?.property_primary_value ?? ''}
					oninput={(e) => {
						if (!netWorth) netWorth = {};
						netWorth.property_primary_value = parseInt((e.target as HTMLInputElement).value) || 0;
					}}
					onchange={saveNetWorth}
					class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/20 w-full"
					placeholder="ex: 350000"
					data-coco-desc="Valeur estimée de votre résidence principale en euros"
				/>
			</label>
			<label class="flex flex-col gap-1.5">
				<span class="text-[11px] text-zinc-400 font-medium">Appréciation annuelle</span>
				<div class="flex items-center gap-2">
					<input
						type="number"
						min="0"
						max="10"
						step="0.5"
						value={netWorth?.property_appreciation_rate != null ? parseFloat(netWorth.property_appreciation_rate) * 100 : '2'}
						oninput={(e) => {
							if (!netWorth) netWorth = {};
							const pct = parseFloat((e.target as HTMLInputElement).value);
							netWorth.property_appreciation_rate = (pct || 2) / 100;
						}}
						onchange={saveNetWorth}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/20 w-20"
						data-coco-desc="Taux d'appréciation annuel de votre bien immobilier"
					/>
					<span class="text-xs text-zinc-500">%/an</span>
				</div>
			</label>
		</div>

		{#if (netWorth?.property_primary_value ?? 0) > 0}
			<div class="mt-3 text-[10px] text-zinc-500 bg-zinc-900/40 rounded-lg p-2">
				<p>Valeur projetée à {profile.target_retirement_age ?? 67} ans :
					<span class="text-emerald-400 font-mono font-bold ml-1">{projectedProperty.toLocaleString('fr-FR')}€</span>
				</p>
				<p class="text-zinc-600 mt-0.5">Avec {((netWorth?.property_appreciation_rate ?? 0.02) * 100).toFixed(1)}%/an sur {(profile.target_retirement_age ?? 67) - (profile.current_age ?? 0)} ans</p>
			</div>
		{/if}

		<label class="flex items-center gap-2 mt-3 text-xs text-zinc-300 cursor-pointer">
			<input
				type="checkbox"
				checked={netWorth?.downsize_enabled ?? false}
				onchange={(e) => {
					if (!netWorth) netWorth = {};
					netWorth.downsize_enabled = (e.target as HTMLInputElement).checked;
					saveNetWorth();
				}}
				class="rounded bg-zinc-700 border-zinc-600 focus:ring-emerald-500/30"
				data-coco-desc="Activer la simulation de downsizing / déménagement"
			/>
			Simuler un déménagement / downsizing
		</label>

		{#if netWorth?.downsize_enabled}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3 p-3 bg-emerald-950/10 border border-emerald-800/20 rounded-lg">
				<label class="flex flex-col gap-1.5">
					<span class="text-[10px] text-zinc-500">Année du déménagement</span>
					<input
						type="number"
						min={new Date().getFullYear()}
						max="2080"
						value={netWorth.downsize_year ?? ''}
						oninput={(e) => {
							netWorth.downsize_year = parseInt((e.target as HTMLInputElement).value) || null;
						}}
						onchange={saveNetWorth}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500/60 w-full"
						data-coco-desc="Année prévue pour le déménagement"
					/>
				</label>
				<label class="flex flex-col gap-1.5">
					<span class="text-[10px] text-zinc-500">Valeur du nouveau bien</span>
					<input
						type="number"
						min="0"
						step="10000"
						value={netWorth.downsize_target_value ?? ''}
						oninput={(e) => {
							netWorth.downsize_target_value = parseInt((e.target as HTMLInputElement).value) || null;
						}}
						onchange={saveNetWorth}
						class="bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500/60 w-full"
						data-coco-desc="Valeur estimée du nouveau bien"
					/>
				</label>
			</div>
			{#if freedCapitalEstimate > 0}
				<div class="mt-2 p-2 bg-emerald-950/20 border border-emerald-800/20 rounded text-[10px] text-emerald-300">
					Capital libéré estimé : <span class="font-mono font-bold">{freedCapitalEstimate.toLocaleString('fr-FR')}€</span>
					<span class="text-zinc-500 ml-1">(après frais de vente ~8% et frais de notaire ~8%)</span>
				</div>
			{/if}
		{/if}
	</Card>

	<!-- Card 6: Parcours conjoint(e) (TASK-7.9) -->
	{#if spouse}
		<Card title={`Parcours de ${spouse.first_name || 'conjoint(e)'}`} icon="📋" accent="purple" dataCocoDesc="Historique d'emploi du conjoint pour le calcul de la retraite">
			{#if spouseCareerSummary}
				<div class="bg-purple-950/20 border border-purple-800/20 rounded-lg p-3 mb-3">
					<div class="flex items-center gap-4 flex-wrap">
						<div class="text-center">
							<span class="block text-lg font-bold font-mono text-purple-300">{spouseCareerSummary.total_trimestres_estimated ?? 0}</span>
							<span class="text-[10px] text-zinc-500">trimestres validés</span>
						</div>
						<div class="text-center">
							<span class="block text-lg font-bold font-mono text-zinc-400">{spouseCareerSummary.trimestres_required ?? 172}</span>
							<span class="text-[10px] text-zinc-500">requis</span>
						</div>
						<div class="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden min-w-[100px]">
							<div
								class="h-full bg-purple-500 rounded-full transition-all duration-500"
								style="width: {Math.min(100, ((spouseCareerSummary.total_trimestres_estimated ?? 0) / (spouseCareerSummary.trimestres_required || 1)) * 100)}%"
							></div>
						</div>
					</div>
				</div>
			{/if}

			{#if spouseCareer.length > 0}
				<div class="space-y-2 mb-3">
					{#each spouseCareer as period (period.id)}
						<div class="flex items-center gap-2 p-2 bg-zinc-900/60 border border-zinc-700/30 rounded-lg" data-coco-desc={`Période conjoint ${period.period_type} ${period.employer_name || ''} ${period.start_date?.substring(0, 4) || ''}-${period.end_date?.substring(0, 4) || 'actuel'}`}>
							<span class="w-2 h-2 rounded-full flex-shrink-0 bg-purple-500"></span>
							<span class="text-xs text-zinc-300 flex-1">
								{period.period_type?.toUpperCase()}
								{#if period.employer_name} — {period.employer_name}{/if}
								{#if period.job_title} ({period.job_title}){/if}
							</span>
							<span class="text-[10px] text-zinc-500">
								{period.start_date?.substring(0, 4) || '?'}–{period.end_date?.substring(0, 4) || 'actuel'}
							</span>
							<span class="text-[10px] text-zinc-500 font-mono">
								{#if period.annual_gross}{parseFloat(period.annual_gross).toLocaleString('fr-FR')}€ brut/an{/if}
							</span>
							<span class="text-[10px] text-zinc-600 bg-zinc-800/40 px-1 py-0.5 rounded">{period.trimestres_estimated ?? 0} trim.</span>
							<button
								class="text-zinc-600 hover:text-rose-400 text-xs"
								onclick={() => deleteSpouseCareerPeriod(period.id)}
								data-coco-desc={`Supprimer la période conjoint ${period.period_type}`}
							>✕</button>
						</div>
					{/each}
				</div>
			{:else}
				<p class="text-xs text-zinc-500 italic mb-2">Aucune période enregistrée pour le conjoint.</p>
			{/if}

			{#if showSpouseCareerForm}
				<div class="flex flex-wrap items-end gap-2 mt-3 p-3 bg-zinc-900/40 border border-zinc-700/30 rounded-lg">
					<select bind:value={newSpCareerType} class="bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200">
						{#each careerTypeOptions as opt}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>
					<input type="date" bind:value={newSpCareerStart} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
					<input type="date" bind:value={newSpCareerEnd} class="w-32 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
					<input type="text" bind:value={newSpCareerEmployer} placeholder="Employeur" class="w-28 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
					<input type="number" bind:value={newSpCareerSalary} min="0" step="1000" placeholder={spSalaryLabel} class="w-28 bg-zinc-800/40 border border-zinc-700/30 rounded px-2 py-1 text-xs text-zinc-200" />
					<button class="bg-purple-600 text-white text-xs rounded px-3 py-1 hover:bg-purple-500" onclick={addSpouseCareerPeriod}>Ajouter</button>
					<button class="text-zinc-500 text-xs" onclick={() => showSpouseCareerForm = false}>Annuler</button>
				</div>
			{:else}
				<button
					class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-purple-700/50 transition-colors mt-2"
					onclick={() => showSpouseCareerForm = true}
					data-coco-desc="Ajouter une période professionnelle pour le conjoint"
				>
					+ Ajouter une période
				</button>
			{/if}
		</Card>
	{/if}
</div>