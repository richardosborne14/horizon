/**
 * Savings page server loader — fetches all 7 investment vehicle allocations.
 * The backend upsert pattern guarantees all 7 rows exist (zero if unset).
 */
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const SESSION_COOKIE = 'session_token';
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
  const sessionToken = cookies.get(SESSION_COOKIE);
  if (!sessionToken) {
    return { allocations: [], total_existing: '0', total_monthly: '0', total_annual: '0' };
  }
  const headers = { Cookie: `${SESSION_COOKIE}=${sessionToken}` };

  const res = await fetch(`${BACKEND_URL}/api/investments`, { headers });

  if (!res.ok) {
    console.error(`[savings] GET /api/investments returned ${res.status}`);
    return {
      allocations: [],
      total_existing: '0',
      total_monthly: '0',
      total_annual: '0',
    };
  }

  const data = await res.json();

  return {
    allocations: data.allocations ?? [],
    total_existing: data.total_existing ?? '0',
    total_monthly: data.total_monthly ?? '0',
    total_annual: data.total_annual ?? '0',
  };
};