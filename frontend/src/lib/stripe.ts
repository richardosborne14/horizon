/**
 * Stripe.js singleton helper — lazy-loads the Stripe client exactly once.
 *
 * WHY a singleton: `loadStripe` triggers a network request to load stripe.js.
 * Calling it multiple times is wasteful; caching the Promise avoids duplicate loads.
 *
 * WHY browser guard: Stripe.js cannot run in Node/SSR context. All callers must
 * be inside `onMount` or client-side event handlers (never in `+page.server.ts`).
 *
 * Usage:
 *   import { getStripe } from '$lib/stripe';
 *   const stripe = await getStripe();  // only inside onMount or click handlers
 */

import { browser } from '$app/environment';
import { PUBLIC_STRIPE_PUBLISHABLE_KEY } from '$env/static/public';
import { loadStripe, type Stripe } from '@stripe/stripe-js';

let _stripePromise: Promise<Stripe | null> | null = null;

/**
 * Lazily initialise and return the Stripe singleton.
 *
 * WHY $env/static/public not $env/dynamic/public:
 *   In Vite dev mode, $env/dynamic/public uses globalThis.__sveltekit_dev.env
 *   which is NEVER set by the server HTML (server uses __sveltekit_HASH instead).
 *   $env/static/public is baked in at compile time and works correctly in both
 *   dev and prod modes without runtime global access.
 *
 * Returns null in SSR/server environments. The caller should handle null gracefully.
 *
 * Returns:
 *   Promise resolving to the Stripe instance, or null if not in browser or key missing.
 */
export function getStripe(): Promise<Stripe | null> {
	if (!browser) return Promise.resolve(null);

	const publishableKey = PUBLIC_STRIPE_PUBLISHABLE_KEY;
	if (!publishableKey || publishableKey.startsWith('pk_test_PLACEHOLDER')) {
		console.warn(
			'[stripe.ts] PUBLIC_STRIPE_PUBLISHABLE_KEY is not set or is a placeholder. ' +
				'Set a real Stripe publishable key in docker-compose.override.yml.'
		);
	}

	if (!_stripePromise) {
		_stripePromise = loadStripe(publishableKey ?? '');
	}
	// Non-null assertion: _stripePromise is assigned above if it was null
	return _stripePromise!;
}
