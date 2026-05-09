<!-- Horizon app layout — sidebar nav with 7 sections -->
<script lang="ts">
	import { navigating, page } from '$app/stores';
	import { onMount } from 'svelte';
	import type { LayoutData } from './$types';

	export let data: LayoutData;

	const SECTIONS = [
		{ id: 'identity', label: 'Identité', icon: '◉' },
		{ id: 'revenue',  label: 'Revenus',  icon: '◈' },
		{ id: 'expenses', label: 'Charges',  icon: '▤' },
		{ id: 'life',     label: 'Vie',      icon: '♦' },
		{ id: 'savings',  label: 'Épargne',  icon: '◆' },
		{ id: 'projects', label: 'Projets',  icon: '⚡' },
		{ id: 'runway',   label: 'Horizon',  icon: '→' },
	];

	$: currentSection = $page.url.pathname.split('/')[1] || 'identity';
</script>

{#if $navigating}
	<div
		class="fixed top-0 left-0 right-0 z-50"
		style="height: 2px; background: var(--color-teal, #2dd4bf);"
		role="progressbar"
		aria-label="Chargement..."
	>
		<div class="h-full animate-pulse" style="background: #2dd4bf66; width: 60%;"></div>
	</div>
{/if}

<div class="min-h-screen bg-zinc-950 text-white" style="font-family: 'Inter', -apple-system, sans-serif;">
	<!-- Header -->
	<header class="border-b border-zinc-800/50 bg-zinc-950/95 backdrop-blur sticky top-0 z-50">
		<div class="max-w-6xl mx-auto px-5 py-3 flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="w-7 h-7 rounded-md bg-gradient-to-br from-teal-400 to-cyan-600 flex items-center justify-center text-[10px] font-extrabold text-white">H</div>
				<div>
					<h1 class="text-sm font-bold tracking-tight">HORIZON</h1>
					<p class="text-[9px] text-zinc-500 tracking-widest uppercase">Moteur patrimonial freelance</p>
				</div>
			</div>
			{#if data.user}
				<p class="text-[10px] text-zinc-600 font-mono">{data.user.name}</p>
			{/if}
		</div>
	</header>

	<div class="max-w-6xl mx-auto flex">
		<!-- Sidebar -->
		<nav class="w-44 flex-shrink-0 border-r border-zinc-800/40 min-h-[calc(100vh-56px)] py-4 px-3 sticky top-14 self-start">
			<div class="space-y-1">
				{#each SECTIONS as section}
					<a href="/{section.id}"
						class="block w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-2 no-underline {currentSection === section.id ? 'bg-zinc-800/60 text-white' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/20'}">
						<span class="text-[10px] w-4 text-center opacity-60">{section.icon}</span>{section.label}
						{#if data.summary?.completeness?.[section.id]}
							<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-auto"></span>
						{/if}
					</a>
				{/each}
			</div>
			<div class="mt-6 space-y-2 border-t border-zinc-800/40 pt-4">
				<p class="text-[9px] text-zinc-600 uppercase tracking-widest font-semibold">Aperçu</p>
				<div class="text-[10px] space-y-1.5 text-zinc-400">
					{#if data.summary}
						<div class="flex justify-between">
							<span>CA/mois</span>
							<span class="font-mono text-teal-300">
								{data.summary.monthly_gross_ca
									? Number(data.summary.monthly_gross_ca).toLocaleString('fr-FR') + '€'
									: '—'}
							</span>
						</div>
						<div class="flex justify-between">
							<span>Enfants</span>
							<span class="font-mono text-zinc-300">{data.summary.kid_count ?? 0}</span>
						</div>
						<div class="flex justify-between">
							<span>Épargne/m</span>
							<span class="font-mono text-teal-300">
								{Number(data.summary.monthly_savings_total || 0).toLocaleString('fr-FR')}€
							</span>
						</div>
						<div class="flex justify-between">
							<span>Projets</span>
							<span class="font-mono text-zinc-300">{data.summary.investment_project_count ?? 0}</span>
						</div>
						{#if data.summary.current_age != null && data.summary.target_retirement_age}
							<div class="pt-2 border-t border-zinc-800/30 mt-2">
								<p class="text-[9px] text-teal-400/70 font-mono">
									{data.summary.current_age} → {data.summary.target_retirement_age} ans · {data.summary.target_retirement_age - data.summary.current_age} ans de runway
								</p>
							</div>
						{:else}
							<div class="pt-2 border-t border-zinc-800/30 mt-2">
								<p class="text-[9px] text-zinc-600">
									<a href="/identity" class="hover:text-teal-400 transition-colors">Renseignez votre date de naissance →</a>
								</p>
							</div>
						{/if}
					{:else}
						<div class="flex justify-between"><span>{data.user?.name ?? 'Utilisateur'}</span></div>
					{/if}
				</div>
			</div>
		</nav>

		<!-- Content -->
		<main class="flex-1 py-5 px-6 min-w-0">
			<slot />
		</main>
	</div>

	<footer class="border-t border-zinc-800/30 py-5 text-center">
		<p class="text-[9px] text-zinc-700 max-w-lg mx-auto">
			Horizon est un simulateur. Ne constitue pas un conseil financier, fiscal ou juridique.
		</p>
	</footer>
</div>