<script lang="ts">
	/**
	 * Reusable SVG area chart — hand-crafted, no library dependency.
	 * 
	 * Used for wealth trajectory and income trajectory on the Runway page.
	 * Subscribes to data via props for reactivity.
	 */
	export let data: Array<{ value: number }> = [];
	export let height = 140;
	export let color = '#2dd4bf'; // teal default
	export let goalLine: number | null = null;
	export let startLabel = '';
	export let endLabel = '';

	const WIDTH = 400;
	let gradientId = '';

	$: gradientId = `grad-${color.replace('#', '')}`;

	$: points = computePoints(data, goalLine);
	$: goalY = computeGoalY(goalLine, data);

	function computePoints(
		vals: Array<{ value: number }>,
		goal: number | null
	): Array<{ x: number; y: number }> {
		if (!vals.length) return [];
		const nums = vals.map((d) => d.value);
		let max = Math.max(...nums);
		let min = Math.min(...nums);
		if (goal !== null) {
			max = Math.max(max, goal);
		}
		if (min > 0) min = 0;
		const range = max - min || 1;
		const chartHeight = height * 0.85;
		const topPadding = height * 0.07;

		return vals.map((d, i) => ({
			x: (i / Math.max(vals.length - 1, 1)) * WIDTH,
			y: height - ((d.value - min) / range) * chartHeight - topPadding
		}));
	}

	function computeGoalY(
		goal: number | null,
		vals: Array<{ value: number }>
	): number | null {
		if (goal === null || !vals.length) return null;
		const nums = vals.map((d) => d.value);
		let max = Math.max(...nums);
		let min = Math.min(...nums);
		if (max < goal) max = goal;
		if (min > 0) min = 0;
		const range = max - min || 1;
		const chartHeight = height * 0.85;
		const topPadding = height * 0.07;
		return height - ((goal - min) / range) * chartHeight - topPadding;
	}

	$: polylinePoints = points.map((p) => `${p.x},${p.y}`).join(' ');
	$: fillPoints =
		points.length > 0
			? polylinePoints +
				` ${WIDTH},${height} 0,${height}`
			: '';
</script>

<svg
	viewBox={`0 0 ${WIDTH} ${height}`}
	preserveAspectRatio="none"
	width="100%"
	class="overflow-visible"
>
	<defs>
		<linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
			<stop offset="0%" stop-color={color} stop-opacity="0.25" />
			<stop offset="100%" stop-color={color} stop-opacity="0" />
		</linearGradient>
	</defs>

	<!-- Area fill -->
	{#if points.length > 0}
		<polygon points={fillPoints} fill={`url(#${gradientId})`} />
		<!-- Line -->
		<polyline
			points={polylinePoints}
			fill="none"
			stroke={color}
			stroke-width="1.5"
			stroke-linejoin="round"
			stroke-linecap="round"
		/>
		<!-- Final point -->
		{#if points.length > 1}
			<circle
				cx={points[points.length - 1].x}
				cy={points[points.length - 1].y}
				r="3"
				fill={color}
			></circle>
		{/if}
	{/if}

	<!-- Goal line -->
	{#if goalLine !== null && goalY !== null}
		<line
			x1="0"
			y1={goalY}
			x2={WIDTH}
			y2={goalY}
			stroke="#f59e0b"
			stroke-width="1"
			stroke-dasharray="6,4"
			opacity="0.6"
		></line>
	{/if}
</svg>

{#if startLabel || endLabel}
	<div class="flex justify-between text-[9px] text-zinc-500 mt-1 px-1">
		<span>{startLabel}</span>
		<span>{endLabel}</span>
	</div>
{/if}