/**
 * Reset password confirm page server actions.
 *
 * Handles POST /reset-password/confirm — receives the token (from email link)
 * and the new password, calls FastAPI to complete the reset.
 *
 * The token is read from the URL query param `?token=xxx` and passed as a
 * hidden form field to avoid exposing it in POST body logs.
 */

import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

interface FormState {
	field: string | null;
	message: string;
	/** True when password reset completed successfully */
	success: boolean;
}

/**
 * Load function: read the reset token from the query string.
 * If no token is present, redirect back to /reset-password.
 *
 * @param url - Request URL (used to extract ?token= param)
 */
export const load: PageServerLoad = async ({ url }) => {
	const token = url.searchParams.get('token') ?? '';

	if (!token) {
		// No token in URL — either expired link or direct access
		redirect(303, '/reset-password');
	}

	return { token };
};

export const actions: Actions = {
	/**
	 * Default form action — completes the password reset.
	 *
	 * @param request - Incoming form POST containing token, password, confirm_password
	 * @returns FormState with success=true, or fail() with error data
	 */
	default: async ({ request }) => {
		const data = await request.formData();
		const token = (data.get('token') as string | null) ?? '';
		const password = (data.get('password') as string | null) ?? '';
		const confirmPassword = (data.get('confirm_password') as string | null) ?? '';

		// --- Server-side fallback validation ---
		if (!token) {
			return fail(400, { field: null, message: 'invalid_token', success: false } satisfies FormState);
		}
		if (password.length < 8) {
			return fail(400, {
				field: 'password',
				message: 'password_too_short',
				success: false
			} satisfies FormState);
		}
		if (password !== confirmPassword) {
			return fail(400, {
				field: 'confirm_password',
				message: 'passwords_no_match',
				success: false
			} satisfies FormState);
		}

		// --- Call FastAPI confirm endpoint ---
		let res: Response;
		try {
			res = await fetch(`${BACKEND_URL}/api/auth/reset-password/confirm`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token, new_password: password })
			});
		} catch (err) {
			console.error('[reset-password/confirm] Network error calling backend:', err);
			return fail(503, { field: null, message: 'network', success: false } satisfies FormState);
		}

		if (!res.ok) {
			let detail = 'generic';
			try {
				const body = await res.json();
				detail = body.detail ?? 'generic';
			} catch {
				// non-JSON error body
			}
			// 400 from the API = invalid or expired token
			const message = res.status === 400 ? 'invalid_token' : detail;
			return fail(res.status, { field: null, message, success: false } satisfies FormState);
		}

		return { field: null, message: '', success: true } satisfies FormState;
	}
};
