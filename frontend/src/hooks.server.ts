import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

/**
 * SvelteKit server hooks for Communauté Coiffure.
 *
 * Two responsibilities:
 * 1. **API reverse proxy** — forwards `/api/` requests to the FastAPI backend.
 *    In Docker, the backend is reachable at `http://backend:8000`.
 *    Without this proxy, browser-side `fetch('/api/...')` and SSR `event.fetch('/api/...')`
 *    would hit the SvelteKit Node server which has no API routes → 404 or ECONNREFUSED.
 *    The Vite dev proxy in `vite.config.ts` only works in `npm run dev` mode,
 *    NOT in the Docker production build (adapter-node). (Task 2.7.6)
 *
 * 2. **Cache-busting headers** — prevents stale HTML/data after Docker rebuilds.
 *    Without this, the browser (and service worker) can serve old HTML from cache
 *    until a hard-refresh is used. (Task 2.7.6)
 */

/**
 * Backend URL for API proxying.
 * - In Docker: `http://backend:8000` (Docker service name, internal network)
 * - Fallback: `http://localhost:8002` (local dev without Docker)
 *
 * WHY not VITE_API_URL: VITE_* vars are baked at BUILD time by Vite.
 * In Docker, the build happens in a builder stage where `localhost:8002` is
 * unreachable. We need a RUNTIME variable. `BACKEND_URL` is set in
 * docker-compose.yml as an environment variable (not a build arg).
 * Falls back to the value from `api.ts` SSR path for consistency.
 */
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export const handle: Handle = async ({ event, resolve }) => {
	// ── API Reverse Proxy ────────────────────────────────────────────────────
	// Intercept ALL /api/* requests and forward them to the FastAPI backend.
	// This handles both browser-side fetches AND SSR event.fetch() calls.
	if (event.url.pathname.startsWith('/api/') || event.url.pathname === '/api') {
		const targetUrl = `${BACKEND_URL}${event.url.pathname}${event.url.search}`;

		try {
			// Forward the request with all headers (cookies, content-type, etc.)
			const headers = new Headers(event.request.headers);
			// Remove host header to avoid confusing the backend
			headers.delete('host');

			const proxyResponse = await fetch(targetUrl, {
				method: event.request.method,
				headers,
				body: event.request.method !== 'GET' && event.request.method !== 'HEAD'
					? await event.request.arrayBuffer()
					: undefined,
				// @ts-ignore — duplex is needed for streaming request bodies in Node 18+
				duplex: 'half',
			});

			// Create a new Response with the proxy response data
			const responseHeaders = new Headers(proxyResponse.headers);
			// Remove transfer-encoding to avoid issues with SvelteKit's response handling
			responseHeaders.delete('transfer-encoding');

			return new Response(proxyResponse.body, {
				status: proxyResponse.status,
				statusText: proxyResponse.statusText,
				headers: responseHeaders,
			});
		} catch (err) {
			console.error(`[API Proxy] Failed to reach backend at ${targetUrl}:`, err);
			return new Response(
				JSON.stringify({ detail: 'Backend service unavailable', status: 'error' }),
				{
					status: 502,
					headers: { 'content-type': 'application/json' },
				}
			);
		}
	}

	// ── Normal SvelteKit request handling ─────────────────────────────────────
	const response = await resolve(event);

	// ── Cache-busting headers ────────────────────────────────────────────────
	const contentType = response.headers.get('content-type') ?? '';
	if (contentType.includes('text/html')) {
		// WHY no-store: prevents the browser AND service worker from caching
		// stale HTML after a Docker rebuild. (Task 2.7.6)
		response.headers.set('cache-control', 'no-store, no-cache, must-revalidate');
	}

	// Also prevent caching of SvelteKit's __data.json responses
	if (event.url.pathname.includes('__data.json')) {
		response.headers.set('cache-control', 'no-store, no-cache, must-revalidate');
	}

	return response;
};
