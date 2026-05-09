/**
 * i18n configuration for Communauté Coiffure.
 *
 * Uses svelte-i18n with lazy-loaded locale files.
 * Default locale: French (fr). Fallback locale: French (fr).
 *
 * Usage in components:
 *   import { t } from 'svelte-i18n';
 *   $t('auth.login.title')
 *
 * Usage in +layout.svelte (SSR-safe):
 *   import { setupI18n } from '$lib/i18n';
 *   setupI18n();
 */

import { browser } from '$app/environment';
import { init, register, locale } from 'svelte-i18n';

const DEFAULT_LOCALE = 'fr';

/**
 * Register locale loaders and initialise svelte-i18n.
 * Must be called once in the root +layout.svelte.
 */
export function setupI18n(): void {
	// Register lazy loaders for each locale
	register('fr', () => import('../../locales/fr.json'));
	register('en', () => import('../../locales/en.json'));

	init({
		// This is a French-only product — always use French.
		// DO NOT detect browser locale: our target users are all in France and
		// an English browser (e.g. Puppeteer, English-locale device) would show
		// English strings throughout.
		fallbackLocale: DEFAULT_LOCALE,
		initialLocale: DEFAULT_LOCALE
	});
}

export { locale };
