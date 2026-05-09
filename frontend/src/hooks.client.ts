/**
 * Client-side hooks — graceful error handling for client-side navigation errors.
 *
 * WHY this file exists:
 *   Without hooks.client.ts, SvelteKit's default client handleError returns a
 *   generic "Internal Error" message. This hook passes through the actual error
 *   message so the +error.svelte page can display something meaningful.
 */
import type { HandleClientError } from '@sveltejs/kit';

export const handleError: HandleClientError = ({ error }) => {
	// Log to console in all environments (visible in browser DevTools)
	console.error('[client] Unhandled navigation error:', error);

	return {
		message: error instanceof Error ? error.message : 'Internal Error'
	};
};
