/**
 * Identity page server loader — loads profile, spouse, career, and AE rate schedule.
 *
 * Sprint 7 (TASK-7.9): Added spouse, CC estimate, and spouse career loading.
 */
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';
const SESSION_COOKIE = 'session_token';

async function fetchWithAuth(cookies: any, fetchFn: typeof fetch, path: string): Promise<any> {
	const token = cookies.get(SESSION_COOKIE);
	const res = await fetchFn(`${BACKEND_URL}${path}`, {
		headers: { Cookie: `${SESSION_COOKIE}=${token}` }
	});
	if (!res.ok) return null;
	return res.json();
}

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	// Fetch profile, user career, user career summary, spouse, net worth
	const [profileJson, careerJson, careerSummary, spouseJson, netWorthJson] = await Promise.all([
		fetchWithAuth(cookies, fetch, '/api/profile'),
		fetchWithAuth(cookies, fetch, '/api/career?owner=user'),
		fetchWithAuth(cookies, fetch, '/api/career/summary?owner=user'),
		fetchWithAuth(cookies, fetch, '/api/spouse'),
		fetchWithAuth(cookies, fetch, '/api/net-worth'),
	]);

	const profile = profileJson;
	const spouse = spouseJson;

	// Fetch spouse career if spouse exists
	let spouseCareer: any[] = [];
	let spouseCareerSummary: any = null;
	let ccEstimate: any = null;

	if (spouse) {
		const [spCareerJson, spCareerSummaryJson] = await Promise.all([
			fetchWithAuth(cookies, fetch, '/api/career?owner=spouse'),
			fetchWithAuth(cookies, fetch, '/api/career/summary?owner=spouse'),
		]);
		spouseCareer = Array.isArray(spCareerJson) ? spCareerJson : [];
		spouseCareerSummary = spCareerSummaryJson;

		// Fetch CC estimate if spouse is CC
		if (spouse.is_conjointe_collaboratrice) {
			const ccRes = await fetch(
				`${BACKEND_URL}/api/spouse/cc-estimate`,
				{
					headers: {
						Cookie: `${SESSION_COOKIE}=${cookies.get(SESSION_COOKIE)}`,
					},
				}
			);
			if (ccRes.ok) {
				ccEstimate = await ccRes.json();
			}
		}
	}

	// Fetch AE rate schedule for the user's current activity type
	const aeType = profile?.ae_activity_type ?? 'bnc_non_reglementee';
	const scheduleRes = await fetch(
		`${BACKEND_URL}/api/rates/ae-schedule?type=${aeType}`,
	);
	let rateSchedule: Array<{ from_year: number; rate: string }> = [];
	if (scheduleRes.ok) {
		const data = await scheduleRes.json();
		rateSchedule = data.schedule ?? [];
	}

	// Fetch all schedules for comparison
	const allSchedulesRes = await fetch(`${BACKEND_URL}/api/rates/ae-schedules`);
	let allSchedules: Record<string, Array<{ from_year: number; rate: string }>> = {};
	if (allSchedulesRes.ok) {
		const data = await allSchedulesRes.json();
		allSchedules = data.schedules ?? {};
	}

	return {
		profile,
		rateSchedule,
		allSchedules,
		careerPeriods: Array.isArray(careerJson) ? careerJson : [],
		careerSummary: careerSummary ?? null,
		spouse,
		spouseCareer,
		spouseCareerSummary,
		ccEstimate,
		netWorth: netWorthJson,
	};
};