/**
 * Expenses page server loader — loads profile expenses, inflation preview, and loans.
 * TASK-6.3: Loans displayed as a new section on the expenses page.
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
	const [expensesData, inflationPreview, loansData, expenseTimelineData] = await Promise.all([
		fetchWithAuth(cookies, '/api/profile/expenses'),
		fetchWithAuth(cookies, '/api/profile/expenses/inflation-preview'),
		fetchWithAuth(cookies, '/api/loans'),
		fetchWithAuth(cookies, '/api/projection/expense-timeline?scale=moderate'),
	]);

	return {
		expenses: expensesData?.expenses ?? {},
		labels: expensesData?.labels ?? {},
		total: expensesData?.total ?? '0',
		inflationPreview: inflationPreview?.preview ?? {},
		currentMonthlyTotal: inflationPreview?.current_monthly_total ?? '0',
		loans: loansData ?? [],
		expenseTimeline: expenseTimelineData ?? null,
	};
};