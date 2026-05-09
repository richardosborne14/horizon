/**
 * Login page server actions.
 *
 * Handles POST /login — validates the form, calls the FastAPI auth endpoint,
 * and forwards the session cookie from FastAPI to the browser.
 *
 * Cookie forwarding is necessary because the form action runs on the Node.js
 * server, not in the browser. The Set-Cookie header from FastAPI must be
 * manually parsed and re-set on the browser response via SvelteKit's cookies API.
 */

import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

/** Session cookie name — must match backend settings.session_cookie_name */
const SESSION_COOKIE = 'session_token';

/** Backend URL for server-side calls (bypasses Caddy, goes direct to container).
 * WHY $env/dynamic/private: reads BACKEND_URL at runtime from the OS environment.
 * docker-compose sets BACKEND_URL=http://backend:8000 (Docker internal network).
 * This overrides frontend/.env at runtime, so the SSR server always reaches the
 * real backend regardless of what localhost port the host uses. (Fixed: 2.7 port sync) */
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

/**
 * Normalised form action return shape.
 * Every fail() call returns this shape so ActionData can be narrowed safely.
 */
interface FormState {
	email: string;
	/** Which field has an error, or null for global API errors */
	field: string | null;
	/** Error message key or raw backend message */
	message: string;
}

/**
 * Load function: redirect already-authenticated users to the dashboard.
 *
 * @param cookies - SvelteKit cookie API
 * @returns Empty object (no data needed by the page)
 */
export const load: PageServerLoad = async ({ cookies }) => {
	if (cookies.get(SESSION_COOKIE)) {
		redirect(303, '/identity');
	}
	return {};
};

export const actions: Actions = {
	/**
	 * Default form action for the login form.
	 *
	 * @param request - Incoming form POST request
	 * @param cookies - SvelteKit cookies API (used to set session cookie)
	 * @returns fail(FormState) with error data, or redirects on success
	 */
	default: async ({ request, cookies }) => {
		const data = await request.formData();
		const email = (data.get('email') as string | null)?.trim() ?? '';
		const password = (data.get('password') as string | null) ?? '';

		// --- Server-side fallback validation (client-side runs first via use:enhance) ---
		if (!email) {
			return fail(400, { email, field: 'email', message: 'required' } satisfies FormState);
		}
		if (!password) {
			return fail(400, { email, field: 'password', message: 'required' } satisfies FormState);
		}

		// --- Call FastAPI auth endpoint ---
		let res: Response;
		try {
			res = await fetch(`${BACKEND_URL}/api/auth/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, password })
			});
		} catch (err) {
			console.error('[login] Network error calling backend:', err);
			return fail(503, { email, field: null, message: 'network' } satisfies FormState);
		}

		if (!res.ok) {
			let detail = 'generic';
			try {
				const body = await res.json();
				detail = body.detail ?? 'generic';
			} catch {
				// non-JSON error body — use generic message
			}
			return fail(res.status, { email, field: null, message: detail } satisfies FormState);
		}

		// --- Forward session cookie from FastAPI → browser ---
		// FastAPI sets Set-Cookie in the response headers.
		// Since this runs server-side, we must manually forward it to the browser.
		const setCookieHeader = res.headers.get('set-cookie');
		let cookieValue = '';
		if (setCookieHeader) {
			// Parse: "session_token=<value>; Path=/; HttpOnly; SameSite=Lax; Max-Age=..."
			cookieValue = setCookieHeader.split(';')[0].split('=').slice(1).join('=');
			cookies.set(SESSION_COOKIE, cookieValue, {
				path: '/',
				httpOnly: true,
				sameSite: 'lax',
				maxAge: 30 * 24 * 60 * 60, // 30 days — matches backend session_expire_days
				// import.meta.env.PROD is set by Vite at build time (true in production builds)
				secure: import.meta.env.PROD
			});
		}

		// --- Determine landing route from preferred_tools (TASK-2.12.3) ---
		// WHY: Comptabilité users shouldn't land on Simulation/Paramétrage.
		// We call the backend with the fresh session cookie before redirect.
		let landingRoute = '/identity';
		if (cookieValue) {
			try {
				const routeRes = await fetch(`${BACKEND_URL}/api/users/me/landing-route`, {
					headers: { Cookie: `${SESSION_COOKIE}=${cookieValue}` }
				});
				if (routeRes.ok) {
					const routeData = await routeRes.json();
					if (typeof routeData.route === 'string' && routeData.route.startsWith('/')) {
						landingRoute = routeData.route;
					}
				}
			} catch (err) {
				// Non-fatal: fall back to /identity silently
				console.warn('[login] Could not determine landing route, using /identity:', err);
			}
		}

		redirect(303, landingRoute);
	}
};
