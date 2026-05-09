/**
 * Reset password request page server actions.
 *
 * Handles POST /reset-password — sends a password reset email via FastAPI.
 * The API always returns 200 regardless of whether the email exists
 * (prevents user enumeration — see FastAPI auth router for rationale).
 */

import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const SESSION_COOKIE = 'session_token';
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

interface FormState {
	email: string;
	field: string | null;
	message: string;
	/** True when the email was sent successfully (show success state) */
	success: boolean;
}

/**
 * Load function: redirect already-authenticated users to dashboard.
 */
export const load: PageServerLoad = async ({ cookies }) => {
	if (cookies.get(SESSION_COOKIE)) {
		redirect(303, '/dashboard');
	}
	return {};
};

export const actions: Actions = {
	/**
	 * Default form action — requests a password reset email.
	 *
	 * @param request - Incoming form POST
	 * @returns FormState with success=true, or fail() with error data
	 */
	default: async ({ request }) => {
		const data = await request.formData();
		const email = (data.get('email') as string | null)?.trim() ?? '';

		if (!email) {
			return fail(400, { email, field: 'email', message: 'required', success: false } satisfies FormState);
		}

		let res: Response;
		try {
			res = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email })
			});
		} catch (err) {
			console.error('[reset-password] Network error calling backend:', err);
			return fail(503, { email, field: null, message: 'network', success: false } satisfies FormState);
		}

		if (!res.ok) {
			let detail = 'generic';
			try {
				const body = await res.json();
				detail = body.detail ?? 'generic';
			} catch {
				// non-JSON error body
			}
			return fail(res.status, { email, field: null, message: detail, success: false } satisfies FormState);
		}

		// API always returns 200 — show success state regardless
		return { email, field: null, message: '', success: true } satisfies FormState;
	}
};
