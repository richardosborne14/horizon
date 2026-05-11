/**
 * Horizon app layout — server load function.
 *
 * Sprint 7 (TASK-7.9): Added spouse loading for household sidebar stats.
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
		if (!res.ok) redirect(303, '/login');
		user = (await res.json()) as User;
	} catch (err) {
		console.error('[app layout] Failed to reach backend:', err);
		redirect(303, '/login?reason=backend_unavailable');
	}

	// Load profile summary for sidebar stats
	let summary: any = null;
	try {
		const summaryRes = await fetch(`${BACKEND_URL}/api/profile/summary`, {
			headers: { Cookie: `${SESSION_COOKIE}=${sessionToken}` }
		});
		if (summaryRes.ok) summary = await summaryRes.json();
	} catch (err) {
		console.error('[app layout] Failed to fetch profile summary:', err);
	}

	// Load spouse for household sidebar (TASK-7.9)
	let spouse: any = null;
	try {
		const spouseRes = await fetch(`${BACKEND_URL}/api/spouse`, {
			headers: { Cookie: `${SESSION_COOKIE}=${sessionToken}` }
		});
		if (spouseRes.ok) spouse = await spouseRes.json();
	} catch {
		// Non-critical — sidebar shows single-person stats
	}

	return { user, summary, spouse };
};