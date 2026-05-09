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
	const [profile, growthData, currentRate] = await Promise.all([
		fetchWithAuth(cookies, '/api/profile'),
		fetchWithAuth(cookies, '/api/constants/growth-presets'),
		fetchWithAuth(cookies, '/api/rates/ae-rate?type=bnc_non_reglementee&year=2026'),
	]);

	// Compute stats row values server-side
	let grossMonthly = 0;
	let cotisationsMonthly = 0;
	let netMonthly = 0;
	let aeRate = '0.262';

	if (profile && profile.monthly_gross_ca) {
		grossMonthly = parseFloat(profile.monthly_gross_ca);
		aeRate = currentRate?.rate ?? '0.262';
		const rateNum = parseFloat(aeRate);
		cotisationsMonthly = Math.round(grossMonthly * rateNum * 100) / 100;
		netMonthly = Math.round((grossMonthly - cotisationsMonthly) * 100) / 100;
	}

	return {
		profile,
		growthPresets: growthData?.presets ?? {},
		stats: { grossMonthly, cotisationsMonthly, netMonthly, aeRate },
	};
};