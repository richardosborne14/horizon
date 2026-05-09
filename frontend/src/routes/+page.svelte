<script lang="ts">
	// Horizon landing — redirect to identity if logged in, otherwise show simple landing
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(async () => {
		try {
			const res = await fetch('/api/users/me');
			if (res.ok) {
				goto('/identity');
			}
		} catch {
			// Not logged in — show landing below
		}
	});
</script>

<svelte:head>
	<title>Horizon — Pilotez votre avenir financier</title>
	<meta name="description" content="Simulateur patrimonial pour freelances français. Projetez vos revenus, charges, épargne et investissements jusqu'à la retraite." />
</svelte:head>

<div class="min-h-screen bg-zinc-950 text-white flex items-center justify-center" style="font-family: 'Inter', -apple-system, sans-serif;">
	<div class="text-center max-w-md px-6">
		<div class="w-14 h-14 rounded-lg bg-gradient-to-br from-teal-400 to-cyan-600 flex items-center justify-center text-lg font-extrabold text-white mx-auto mb-6">H</div>
		<h1 class="text-3xl font-bold tracking-tight mb-3">Horizon</h1>
		<p class="text-zinc-400 text-sm mb-8 leading-relaxed">
			Moteur patrimonial multi-décennal pour freelances français.
		</p>
		<div class="flex gap-3 justify-center">
			<a href="/login" class="px-5 py-2.5 rounded-lg bg-teal-500/15 border border-teal-500/30 text-teal-300 text-sm font-medium hover:bg-teal-500/20 transition-colors">Connexion</a>
			<a href="/register" class="px-5 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm font-medium hover:bg-zinc-700 transition-colors">Créer un compte</a>
		</div>
		<p class="text-[10px] text-zinc-600 mt-10">
			Simulateur uniquement. Ne constitue pas un conseil financier, fiscal ou juridique.
		</p>
	</div>
</div>