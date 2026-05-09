<script lang="ts">
	import '../app.css';
	import { setupI18n } from '$lib/i18n';
	import { isLoading } from 'svelte-i18n';
	import { afterNavigate } from '$app/navigation';

	// Initialise i18n once at the root layout level.
	// All child routes inherit the active locale automatically.
	setupI18n();

	// Scroll to top on every real cross-page navigation.
	// TASK-2.12.10: Eric reported that navigating between pages left the user
	// mid-page (SvelteKit preserves scroll position by default).
	// Exceptions: popstate (back/forward — browser restores scroll itself)
	// and same-pathname navigations (in-page anchor links like #section).
	afterNavigate(({ from, to, type }) => {
		// Let the browser handle back/forward scroll restoration
		if (type === 'popstate') return;
		// Don't disrupt in-page anchor navigation
		if (from?.url.pathname === to?.url.pathname) return;
		// Scroll to top instantly (no smooth — would be jarring on every nav)
		window.scrollTo({ top: 0, behavior: 'instant' });
	});
</script>

{#if $isLoading}
	<!-- Brief flash while locale JSON loads — keeps layout stable -->
	<div style="display:contents"></div>
{:else}
	<slot />
{/if}
