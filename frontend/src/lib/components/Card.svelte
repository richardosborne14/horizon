<script lang="ts">
	/** Reusable card component with accent border from the Horizon prototype.
	 *  @component
	 *  Usage: <Card title="Vous" icon="👤" accent="teal"> ... </Card>
	 */
	export let title: string;
	export let icon: string | undefined = undefined;
	export let accent: 'teal' | 'amber' | 'emerald' | 'rose' | 'purple' = 'teal';
	export let dataCocoDesc: string = '';

	const accentColors: Record<string, string> = {
		teal: 'border-teal-500/40',
		amber: 'border-amber-500/40',
		emerald: 'border-emerald-500/40',
		rose: 'border-rose-500/40',
		purple: 'border-purple-500/40',
	};

	const accentBgs: Record<string, string> = {
		teal: 'bg-teal-950/20',
		amber: 'bg-amber-950/20',
		emerald: 'bg-emerald-950/20',
		rose: 'bg-rose-950/20',
		purple: 'bg-purple-950/20',
	};
</script>

<div class="border-l-2 {accentColors[accent]} {accentBgs[accent]} border border-zinc-800/40 border-l-2 rounded-xl p-5" data-coco-desc={dataCocoDesc}>
	{#if title}
		<div class="flex items-center gap-2 mb-4">
			{#if icon}
				<span class="text-sm">{icon}</span>
			{/if}
			<h2 class="text-sm font-semibold text-zinc-200">{title}</h2>
		</div>
	{/if}
	<slot />
</div>