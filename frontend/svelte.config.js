import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Preprocessor: handles TypeScript and PostCSS/Tailwind in .svelte files
	preprocess: vitePreprocess(),

	// Disable Svelte 5 runes mode — compile in legacy (Svelte 4) mode.
	// WHY: svelte-i18n@4.x creates Svelte stores that rely on the Svelte 4
	// store subscribe protocol. Svelte 5 runes mode rewrites how stores are
	// consumed: `$propName` inside function arguments (e.g. `$_($titleKey, '')`)
	// is misinterpreted as store autosubscription, causing:
	//   Uncaught TypeError: store.subscribe is not a function
	// Setting runes: false forces Svelte 5 to compile .svelte files in full
	// legacy mode, preserving `$:` reactive statements, `$store` autosubscription,
	// and the old store protocol that svelte-i18n depends on.
	// The project already uses Svelte 4 syntax throughout (LEARNINGS #13).
	compilerOptions: {
		runes: false
	},

	kit: {
		// adapter-node builds for Node.js — used in Docker
		adapter: adapter(),

		// WHY: Version polling detects new deployments and triggers auto-reload.
		// Fixes the stale-page-after-rebuild bug (Task 2.7.6). SvelteKit checks
		// for a version mismatch every 60s; on mismatch, next navigation reloads
		// the page from the server instead of using client-side routing.
		version: {
			pollInterval: 60000
		},

		// Path aliases: $lib → src/lib
		alias: {
			$lib: 'src/lib',
			$styles: 'src/styles',
			$config: 'src/config',
			$locales: 'src/locales'
		}
	}
};

export default config;
