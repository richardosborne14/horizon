/**
 * Revenue page server loader — loads profile, growth presets, and current AE rate.
 */
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';
const SESSION_COOKIE = 'session_token';

async function fetchWithAuth(cookies: any, path: string): Promise<any> {
	const token = cookies.get(SESSION_COOKIE);
	const res = await fetch(`${BACKEND_URL}${path}`, {
		headers: { Cookie: `${SESSION_COOKIE}=${token}` }
	});
	if (!res.ok) return null;
	return res.json();
}

export const load: PageServerLoad = async ({ cookies }) => {
	const [profile, growthData, currentRate, waterfallData, sourcesData] = await Promise.all([
		fetchWithAuth(cookies, '/api/profile'),
		fetchWithAuth(cookies, '/api/constants/growth-presets'),
		fetchWithAuth(cookies, '/api/rates/ae-rate?type=bnc_non_reglementee&year=2026'),
		fetchWithAuth(cookies, '/api/profile/waterfall'),
		fetchWithAuth(cookies, '/api/income-sources'),
	]);

	const incomeSources: any[] = sourcesData?.items ?? sourcesData ?? [];

	// Compute stats row values from income sources (user AE revenue only)
	let grossMonthly = 0;
	let cotisationsMonthly = 0;
	let netMonthly = 0;
	let aeRate = currentRate?.rate ?? '0.262';
	const rateNum = parseFloat(aeRate);

	for (const src of incomeSources) {
		if (!src.is_active) continue;
		if (src.earner !== 'user') continue;
		if (!src.is_ae_revenue) continue;
		if (src.source_type === 'salary') continue; // salaried income isn't AE CA

		const amt = parseFloat(src.amount) || 0;
		if (src.frequency === 'annual') {
			grossMonthly += amt / 12;
		} else if (src.frequency === 'monthly') {
			grossMonthly += amt;
		}
		// one_time sources don't contribute to monthly stats
	}

	grossMonthly = Math.round(grossMonthly * 100) / 100;
	cotisationsMonthly = Math.round(grossMonthly * rateNum * 100) / 100;
	netMonthly = Math.round((grossMonthly - cotisationsMonthly) * 100) / 100;

	return {
		profile,
		growthPresets: growthData?.presets ?? {},
		stats: { grossMonthly, cotisationsMonthly, netMonthly, aeRate },
		incomeSources,
		waterfall: waterfallData ?? null,
	};
};
