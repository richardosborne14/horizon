/**
 * Identity page server loader — loads profile and AE rate schedule.
 *
 * Runs on the server before rendering the Identity page.
 * Fetches the authenticated user's profile (auto-creates if new)
 * and the AE rate schedule for their current activity type.
 */
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';
const SESSION_COOKIE = 'session_token';

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	const sessionToken = cookies.get(SESSION_COOKIE);

	// Fetch profile (auto-creates on first access)
	const profileRes = await fetch(`${BACKEND_URL}/api/profile`, {
		headers: { Cookie: `${SESSION_COOKIE}=${sessionToken}` }
	});

	let profile = null;
	if (profileRes.ok) {
		profile = await profileRes.json();
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
	};
};