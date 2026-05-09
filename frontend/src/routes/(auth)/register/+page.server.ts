/**
 * Register page server actions.
 *
 * Handles POST /register — creates a new account via the FastAPI endpoint,
 * sets the session cookie, and redirects to onboarding.
 *
 * Uses the same cookie-forwarding pattern as login/+page.server.ts.
 * See LEARNINGS.md for the rationale behind manual cookie forwarding.
 */

import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const SESSION_COOKIE = 'session_token';
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

interface FormState {
	email: string;
	name: string;
	field: string | null;
	message: string;
}

/**
 * Load function: redirect already-authenticated users to the dashboard.
 */
export const load: PageServerLoad = async ({ cookies }) => {
	if (cookies.get(SESSION_COOKIE)) {
		redirect(303, '/dashboard');
	}
	return {};
};

export const actions: Actions = {
	/**
	 * Default form action for the registration form.
	 *
	 * @param request - Incoming form POST request
	 * @param cookies - SvelteKit cookies API (used to set session cookie)
	 * @returns fail(FormState) with error data, or redirects to /onboarding on success
	 */
	default: async ({ request, cookies }) => {
		const data = await request.formData();
		const name = (data.get('name') as string | null)?.trim() ?? '';
		const email = (data.get('email') as string | null)?.trim() ?? '';
		const password = (data.get('password') as string | null) ?? '';
		const confirmPassword = (data.get('confirm_password') as string | null) ?? '';

		// --- Server-side fallback validation ---
		if (!name) {
			return fail(400, { name, email, field: 'name', message: 'required' } satisfies FormState);
		}
		if (!email) {
			return fail(400, { name, email, field: 'email', message: 'required' } satisfies FormState);
		}
		if (password.length < 8) {
			return fail(400, {
				name,
				email,
				field: 'password',
				message: 'password_too_short'
			} satisfies FormState);
		}
		if (password !== confirmPassword) {
			return fail(400, {
				name,
				email,
				field: 'confirm_password',
				message: 'passwords_no_match'
			} satisfies FormState);
		}

		// --- Call FastAPI register endpoint ---
		let res: Response;
		try {
			res = await fetch(`${BACKEND_URL}/api/auth/register`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, password, name })
			});
		} catch (err) {
			console.error('[register] Network error calling backend:', err);
			return fail(503, { name, email, field: null, message: 'network' } satisfies FormState);
		}

		if (!res.ok) {
			let detail = 'generic';
			try {
				const body = await res.json();
				detail = body.detail ?? 'generic';
			} catch {
				// non-JSON error body
			}
			// 409 = email already taken
			const field = res.status === 409 ? 'email' : null;
			return fail(res.status, { name, email, field, message: detail } satisfies FormState);
		}

		// --- Forward session cookie from FastAPI → browser ---
		const setCookieHeader = res.headers.get('set-cookie');
		if (setCookieHeader) {
			const cookieValue = setCookieHeader.split(';')[0].split('=').slice(1).join('=');
			cookies.set(SESSION_COOKIE, cookieValue, {
				path: '/',
				httpOnly: true,
				sameSite: 'lax',
				maxAge: 30 * 24 * 60 * 60,
				secure: import.meta.env.PROD
			});
		}

		// New users go through onboarding
		redirect(303, '/onboarding');
	}
};
