/**
 * Pilotage context utility — fetches annual summary for the current year
 * and computes pre-fill values for calculator inputs.
 *
 * WHY: Users should not have to re-type numbers they've already entered in
 * pilotage. This utility bridges pilotage data into standalone calculators,
 * implementing the "show the chain" cross-cutting UX requirement.
 *
 * Usage:
 *   const ctx = await getPilotageContext(salonId);
 *   if (ctx) caAnnuel = String(ctx.annualised_ca);
 *
 * Task: TASK-2.9.8.3 — /prix + /taxes prefill from pilotage annual
 */

import { api } from '$lib/api';

/** Pre-computed pilotage context for calculator prefill. */
export interface PilotageContext {
	/** The year this context covers. */
	year: number;
	/** YTD sum of ca_realise_ttc across all months with data. */
	total_ca: number;
	/** Number of months that have actual data (ca_realise_ttc > 0). */
	months_with_data: number;
	/** Average monthly CA = total_ca / months_with_data. */
	avg_monthly_ca: number;
	/** Annualised estimate = avg_monthly_ca * 12. */
	annualised_ca: number;
	/** Human-readable badge label for display in ProvenanceBadge. */
	badge_label: string;
}

/** Minimal shape of the annual summary API response we care about. */
interface AnnualSummaryRaw {
	year: number;
	total_ca: string | number;
	months_with_data: number;
}

/**
 * Fetch pilotage annual summary for the current year and compute
 * pre-fill values for calculator inputs.
 *
 * Returns null if:
 * - The salon has no pilotage data for the year (months_with_data === 0).
 * - total_ca is zero or negative (no meaningful average to project).
 * - The API fails for any reason (graceful degradation — never throws).
 *
 * WHY never throws: prefill is a UX nicety, not a critical dependency.
 * A broken API must never block the user from running a calculation manually.
 *
 * @param salonId - UUID of the active salon.
 * @returns Pre-computed PilotageContext or null.
 */
export async function getPilotageContext(salonId: string): Promise<PilotageContext | null> {
	const year = new Date().getFullYear();

	try {
		const raw = await api.get<AnnualSummaryRaw>(`/salons/${salonId}/annual-summary/${year}`);

		const total_ca = Number(raw.total_ca) || 0;
		const months_with_data = raw.months_with_data || 0;

		// Need at least 1 month with real data to produce a meaningful average.
		if (months_with_data === 0 || total_ca <= 0) {
			return null;
		}

		const avg_monthly_ca = total_ca / months_with_data;
		// Round annualised figure to nearest euro — avoids confusing "42 345.83 €"
		const annualised_ca = Math.round(avg_monthly_ca * 12);

		const badge_label = `Depuis pilotage ${year} — ${months_with_data} mois de données`;

		return {
			year,
			total_ca,
			months_with_data,
			avg_monthly_ca,
			annualised_ca,
			badge_label
		};
	} catch {
		// Graceful degradation — API errors must never break calculator pages.
		return null;
	}
}

/**
 * Format a number as a French locale integer string (no currency symbol).
 * Used for human-readable values in provenance badge labels.
 *
 * @param n - Number to format.
 * @returns French locale formatted string, e.g. "42 000".
 */
export function formatAmountFr(n: number): string {
	return new Intl.NumberFormat('fr-FR', {
		maximumFractionDigits: 0
	}).format(n);
}
