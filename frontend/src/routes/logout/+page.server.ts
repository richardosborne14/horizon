/**
 * Logout route — handles the form POST from the sidebar logout button.
 *
 * Flow:
 *   1. Read session cookie
 *   2. Call POST /api/auth/logout on the backend (destroys the DB session record)
 *   3. Delete the SvelteKit session cookie
 *   4. Redirect to /login
 *
 * This is a form action endpoint only — there is no GET page.
 * The form in Sidebar.svelte and MobileNav.svelte posts to this route.
 */

import { redirect } from '@sveltejs/kit';
import type { Actions } from './$types';
import { env } from '$env/dynamic/private';

/** Session cookie name — must match backend settings.session_cookie_name */
const SESSION_COOKIE = 'session_token';

/** Backend URL for server-side calls */
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export const actions: Actions = {
	/**
	 * Default logout action.
	 * Calls the backend to invalidate the session, then clears the cookie.
	 *
	 * @param cookies - SvelteKit cookies API
	 * @returns Redirect to /login on success (or if session was already invalid)
	 */
	default: async ({ cookies }) => {
		const sessionToken = cookies.get(SESSION_COOKIE);

		if (sessionToken) {
			// Attempt to invalidate the session on the backend.
			// We don't fail hard if the backend call errors — the local cookie
			// deletion is the important part. A stale server session will expire
			// naturally after session_expire_days.
			try {
				await fetch(`${BACKEND_URL}/api/auth/logout`, {
					method: 'POST',
					headers: {
						Cookie: `${SESSION_COOKIE}=${sessionToken}`
					}
				});
			} catch (err) {
				// Network error — log and proceed with cookie deletion
				console.error('[logout] Failed to reach backend for session invalidation:', err);
			}

			// Always delete the local cookie regardless of backend response
			cookies.delete(SESSION_COOKIE, { path: '/' });
		}

		// Redirect to login after logout
		redirect(303, '/login');
	}
};
