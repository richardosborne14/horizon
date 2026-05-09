/**
 * Typed API client for communicating with the FastAPI backend.
 *
 * All requests go through this module to ensure:
 * - Consistent error handling
 * - Automatic credential (cookie) forwarding
 * - Type-safe request/response handling
 * - Single place to update base URL
 *
 * Usage:
 *   import { api } from '$lib/api';
 *   const user = await api.get<User>('/users/me');
 *   await api.post('/auth/login', { email, password });
 */

import { browser } from '$app/environment';

// Base URL: in browser use relative path (same origin via proxy), in SSR use runtime env.
// WHY process.env first: VITE_API_URL is `http://localhost:8002` which is unreachable
// inside Docker. docker-compose.yml sets BACKEND_URL=http://backend:8000. (Task 2.7.6)
const BASE_URL = browser
	? '/api'
	: ((typeof process !== 'undefined' && process.env?.BACKEND_URL) || import.meta.env.VITE_API_URL || 'http://backend:8000') + '/api';

/** Standard API error shape from FastAPI */
export interface ApiError {
	detail: string;
	code?: string;
}

/** Typed wrapper around a failed API response */
export class ApiRequestError extends Error {
	constructor(
		public readonly status: number,
		public readonly detail: string,
		public readonly code?: string
	) {
		super(detail);
		this.name = 'ApiRequestError';
	}
}

/**
 * Core fetch wrapper. Handles JSON serialisation, cookie forwarding,
 * and converts non-2xx responses to thrown ApiRequestError.
 *
 * @param path - API path (without /api prefix), e.g. '/auth/login'
 * @param options - Fetch options (method, body, headers, etc.)
 * @returns Parsed JSON response body
 * @throws ApiRequestError on non-2xx responses
 */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
	const url = `${BASE_URL}${path}`;

	const response = await fetch(url, {
		...options,
		// Always forward cookies (session token lives here)
		credentials: 'include',
		headers: {
			'Content-Type': 'application/json',
			...options.headers
		}
	});

	// 204 No Content — return empty
	if (response.status === 204) {
		return undefined as T;
	}

	let body: unknown;
	try {
		body = await response.json();
	} catch {
		// Non-JSON response (e.g. server error HTML)
		throw new ApiRequestError(response.status, `Server error: ${response.status}`);
	}

	if (!response.ok) {
		const err = body as ApiError;
		throw new ApiRequestError(response.status, err.detail ?? 'Une erreur est survenue', err.code);
	}

	return body as T;
}

/**
 * API client object with typed convenience methods.
 * All methods return parsed response body.
 */
export const api = {
	/**
	 * GET request.
	 * @param path - API path
	 * @param params - Optional query parameters
	 */
	get<T>(path: string, params?: Record<string, string>): Promise<T> {
		const url = params ? `${path}?${new URLSearchParams(params)}` : path;
		return request<T>(url, { method: 'GET' });
	},

	/**
	 * POST request with JSON body.
	 * @param path - API path
	 * @param body - Request body (will be JSON-serialised)
	 */
	post<T>(path: string, body?: unknown): Promise<T> {
		return request<T>(path, {
			method: 'POST',
			body: body !== undefined ? JSON.stringify(body) : undefined
		});
	},

	/**
	 * PUT request with JSON body.
	 * @param path - API path
	 * @param body - Request body (will be JSON-serialised)
	 */
	put<T>(path: string, body?: unknown): Promise<T> {
		return request<T>(path, {
			method: 'PUT',
			body: body !== undefined ? JSON.stringify(body) : undefined
		});
	},

	/**
	 * PATCH request with JSON body.
	 * @param path - API path
	 * @param body - Partial update body
	 */
	patch<T>(path: string, body?: unknown): Promise<T> {
		return request<T>(path, {
			method: 'PATCH',
			body: body !== undefined ? JSON.stringify(body) : undefined
		});
	},

	/**
	 * DELETE request.
	 * @param path - API path
	 */
	delete<T>(path: string): Promise<T> {
		return request<T>(path, { method: 'DELETE' });
	}
};
