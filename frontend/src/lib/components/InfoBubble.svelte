<script lang="ts">
	/**
	 * InfoBubble — contextual help tooltip for beginner users.
	 *
	 * Shows a Lucide Info icon. On desktop (hover-capable): hover reveals tooltip.
	 * On mobile (touch-only): tap toggles open/closed; tap outside closes.
	 *
	 * WHY the hover guard: on iOS Safari, a tap fires both mouseenter AND click
	 * in rapid succession. Without the guard, mouseenter sets open=true, then
	 * click calls toggle() → open=false — the tooltip never stays open on touch.
	 * We check window.matchMedia('(hover: hover)') to determine device capability.
	 *
	 * WHY click-outside listener: on touch devices there's no mouseleave,
	 * so we listen for document clicks outside the container to auto-close.
	 *
	 * @prop text     - The help text to display (plain French, concise).
	 * @prop size     - Icon size in px (default: 14).
	 * @prop position - Tooltip position: 'top' | 'bottom' | 'right' (default: 'top').
	 */
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { Info } from 'lucide-svelte';

	export let text: string;
	export let size: number = 14;
	export let position: 'top' | 'bottom' | 'right' = 'top';

	let open = false;
	let containerEl: HTMLSpanElement;

	/**
	 * True if the device supports true hover (mouse/trackpad).
	 * WHY: window.matchMedia evaluated lazily so it's always current.
	 */
	function canHover(): boolean {
		return browser ? window.matchMedia('(hover: hover)').matches : false;
	}

	function toggle() {
		open = !open;
	}

	function close() {
		open = false;
	}

	/**
	 * mouseenter handler — only opens on hover-capable devices.
	 * WHY: On touch devices this event fires before click, causing open→toggle→close
	 * in a single tap. Guarding with canHover() makes it a no-op on touch.
	 */
	function handleMouseEnter() {
		if (canHover()) open = true;
	}

	/**
	 * mouseleave handler — only closes on hover-capable devices.
	 * Touch devices rely on click-outside to close.
	 */
	function handleMouseLeave() {
		if (canHover()) open = false;
	}

	/**
	 * Document click listener — closes tooltip when user taps/clicks outside.
	 * WHY: on touch devices there's no mouseleave, so without this the tooltip
	 * would stay open forever after the user taps elsewhere.
	 * stopPropagation on the container's click means outside clicks reach the
	 * document handler without interference.
	 */
	function handleDocClick(e: MouseEvent) {
		if (open && containerEl && !containerEl.contains(e.target as Node)) {
			open = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}

	onMount(() => {
		if (browser) {
			document.addEventListener('click', handleDocClick);
		}
	});

	onDestroy(() => {
		if (browser) {
			document.removeEventListener('click', handleDocClick);
		}
	});

	$: positionClasses =
		position === 'top'
			? 'bottom-full left-1/2 -translate-x-1/2 mb-2'
			: position === 'bottom'
			? 'top-full left-1/2 -translate-x-1/2 mt-2'
			: 'left-full top-1/2 -translate-y-1/2 ml-2';
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<span
	bind:this={containerEl}
	class="relative inline-flex items-center"
	on:mouseenter={handleMouseEnter}
	on:mouseleave={handleMouseLeave}
	data-coco-desc="Bulle d'aide : {text}"
>
	<button
		type="button"
		class="inline-flex items-center justify-center rounded-full transition-colors"
		style="color: var(--color-primary-400, #a78bfa); background: transparent; border: none; padding: 1px; cursor: help;"
		aria-label="Aide — {text}"
		aria-expanded={open}
		tabindex="0"
		on:click|stopPropagation={toggle}
		on:focus={() => (open = true)}
		on:blur={close}
		on:keydown={handleKeydown}
	>
		<Info {size} aria-hidden="true" />
	</button>

	{#if open}
	<div
		class="absolute z-50 rounded-lg px-3 py-2 text-xs shadow-lg pointer-events-none {positionClasses}"
		style="
			background: var(--color-text-primary, #1e1b4b);
			color: #fff;
			max-width: 240px;
			min-width: 150px;
			line-height: 1.5;
			white-space: normal;
			border: none;
		"
		role="tooltip"
	>
		{text}
		<!-- Arrow -->
		{#if position === 'top'}
		<div class="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0"
			style="border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid var(--color-text-primary, #1e1b4b);">
		</div>
		{:else if position === 'bottom'}
		<div class="absolute left-1/2 -translate-x-1/2 bottom-full w-0 h-0"
			style="border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 5px solid var(--color-text-primary, #1e1b4b);">
		</div>
		{:else if position === 'right'}
		<div class="absolute right-full top-1/2 -translate-y-1/2 w-0 h-0"
			style="border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-right: 5px solid var(--color-text-primary, #1e1b4b);">
		</div>
		{/if}
	</div>
	{/if}
</span>
