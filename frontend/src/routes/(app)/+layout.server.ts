/**
 * Horizon app layout — server load function.
 *
 * Runs on every request to any route inside (app)/.
 * Responsibilities:
 *   1. Check session cookie — redirect to /login if missing
 *   2. Verify session is still valid by calling GET /api/users/me
 *   3. Return { user } — available to all child routes via $page.data
 */
import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';
import type { User } from '$lib/types';
import { env } from '$env/dynamic/private';

const SESSION_COOKIE = 'session_token';
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export const load: LayoutServerLoad = async ({ cookies, fetch, url }) => {
	const sessionToken = cookies.get(SESSION_COOKIE);

	if (!sessionToken) {
		redirect(303, '/login');
	}

	let user: User;
	try {
		const res = await fetch(`${BACKEND_URL}/api/users/me`, {
			headers: { Cookie: `${SESSION_COOKIE}=${sessionToken}` }
		});

		if (res.status === 401) {
			cookies.delete(SESSION_COOKIE, { path: '/' });
			redirect(303, '/login?reason=session_expired');
		}

		if (!res.ok) {
			console.error(`[app layout] GET /api/users/me returned ${res.status}`);
			redirect(303, '/login');
		}

		user = (await res.json()) as User;
	} catch (err) {
		console.error('[app layout] Failed to reach backend:', err);
		redirect(303, '/login?reason=backend_unavailable');
	}


	// Load profile summary for sidebar stats
	let summary = null;
	try {
		const summaryRes = await fetch(`${BACKEND_URL}/api/profile/summary`, {
			headers: { Cookie: `${SESSION_COOKIE}=${sessionToken}` }
		});
		if (summaryRes.ok) {
			summary = await summaryRes.json();
		}
	} catch (err) {
		// Non-critical — sidebar shows dashes if summary unavailable
		console.error('[app layout] Failed to fetch profile summary:', err);
	}

	return { user, summary };
};