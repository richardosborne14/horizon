/**
 * Control Panel — server load function.
 *
 * Loads deployment.json and pings each service health endpoint.
 * Returns service statuses to the page for display in the Deployment tab.
 *
 * Health checks run in parallel with a 3-second timeout each.
 * A failed or timeout ping shows "hors ligne" — never crashes the page.
 */

import type { PageServerLoad } from './$types';
/*
 * WHY: deployment.json lives at the project root, outside the frontend/ Docker
 * build context (context: ./frontend). A copy is kept at
 * src/config/deployment.json — update that copy whenever deployment.json changes.
 */
import deploymentConfig from '../../../config/deployment.json';

/** Result of a single health check ping. */
interface ServiceStatus {
	id: string;
	name: string;
	description: string;
	tech: string;
	health_endpoint: string | null;
	status: 'ok' | 'error' | 'unknown';
	latency_ms: number | null;
	error: string | null;
}

/**
 * Pings a single health endpoint and returns a ServiceStatus.
 * Times out after 3 seconds — we don't want slow checks to block the page.
 *
 * @param service - Service definition from deployment.json
 * @returns ServiceStatus with status and latency_ms
 */
async function pingService(service: (typeof deploymentConfig.services)[number]): Promise<ServiceStatus> {
	const base: ServiceStatus = {
		id: service.id,
		name: service.name,
		description: service.description,
		tech: service.tech,
		health_endpoint: service.health_endpoint,
		status: 'unknown',
		latency_ms: null,
		error: null
	};

	// Services without a health endpoint (e.g. database via Docker, Caddy) are always unknown
	if (!service.health_endpoint) {
		return { ...base, status: 'unknown', error: 'Pas de point de santé configuré' };
	}

	const start = Date.now();
	try {
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), 3000);

		const res = await fetch(service.health_endpoint, {
			signal: controller.signal,
			headers: { Accept: 'application/json' }
		});

		clearTimeout(timeout);
		const latency_ms = Date.now() - start;

		if (res.ok) {
			return { ...base, status: 'ok', latency_ms };
		} else {
			return { ...base, status: 'error', latency_ms, error: `HTTP ${res.status}` };
		}
	} catch (err: unknown) {
		const latency_ms = Date.now() - start;
		const message = err instanceof Error ? err.message : 'Erreur inconnue';
		return { ...base, status: 'error', latency_ms, error: message };
	}
}

export const load: PageServerLoad = async () => {
	// Ping all services in parallel — non-fatal if any fail
	const statuses = await Promise.all(deploymentConfig.services.map(pingService));

	return {
		statuses,
		checked_at: new Date().toISOString(),
		project: deploymentConfig.project,
		version: deploymentConfig.version,
		environments: deploymentConfig.environments
	};
};
