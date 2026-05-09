/**
 * Admin layout — server load function.
 *
 * Guards ALL routes under (admin)/ — only logged-in users with role='admin'
 * can access them. All other users are redirected away.
 *
 * This runs before any (admin) page load function.
 */

import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';
import type { User } from '$lib/types';
import { env } from '$env/dynamic/private';

const SESSION_COOKIE = 'session_token';
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export const load: LayoutServerLoad = async ({ cookies, fetch }) => {
	const sessionToken = cookies.get(SESSION_COOKIE);

	// No session cookie — redirect to login
	if (!sessionToken) {
		redirect(303, '/login');
	}

	// Verify session and fetch user profile
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
			console.error(`[admin layout] GET /api/users/me returned ${res.status}`);
			redirect(303, '/login');
		}

		user = (await res.json()) as User;
	} catch (err) {
		console.error('[admin layout] Failed to reach backend:', err);
		redirect(303, '/login?reason=backend_unavailable');
	}

	// Admin-only gate — non-admin users are redirected to the dashboard
	// WHY: We redirect rather than 403 to avoid exposing that the route exists.
	if (user.role !== 'admin') {
		redirect(303, '/dashboard');
	}

	return { user };
};
