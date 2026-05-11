/**
 * Runway page server loader — fetches projection + profile data.
 */
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const SESSION_COOKIE = 'session_token';
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
  const sessionToken = cookies.get(SESSION_COOKIE);
  if (!sessionToken) {
    return { projection: null, profile: null, error: 'no_session' };
  }
  const headers = { Cookie: `${SESSION_COOKIE}=${sessionToken}` };

  // Fetch profile for goal value, world_scale, birth_date
  const profileRes = await fetch(`${BACKEND_URL}/api/profile`, { headers });
  if (!profileRes.ok) {
    console.error(`[runway] GET /api/profile returned ${profileRes.status}`);
    return { projection: null, profile: null, error: 'no_profile' };
  }
  const profile = await profileRes.json();

  // TASK-7.14: Fetch all 3 projection scales in parallel for confidence bands
  const scale = profile?.world_scale || 'moderate';
  const [optRes, modRes, pesRes] = await Promise.all([
    fetch(`${BACKEND_URL}/api/projection?scale=optimistic`, { headers }),
    fetch(`${BACKEND_URL}/api/projection?scale=moderate`, { headers }),
    fetch(`${BACKEND_URL}/api/projection?scale=pessimistic`, { headers }),
  ]);

  let projections: Record<string, any> | null = null;
  if (optRes.ok && modRes.ok && pesRes.ok) {
    projections = {
      optimistic: await optRes.json(),
      moderate: await modRes.json(),
      pessimistic: await pesRes.json(),
    };
  }

  // Fallback: if all 3 failed, try single fetch for backward compat
  if (!projections) {
    const singleRes = await fetch(
      `${BACKEND_URL}/api/projection?scale=${scale}`,
      { headers }
    );
    if (singleRes.ok) {
      projections = {
        optimistic: null,
        moderate: await singleRes.json(),
        pessimistic: null,
      };
    } else {
      console.error(`[runway] GET /api/projection returned ${singleRes.status}`);
      return {
        projection: null,
        profile,
        error: singleRes.status === 404 ? 'no_profile' : singleRes.status === 422 ? 'no_birthdate' : 'api_error'
      };
    }
  }

  // mainProjection is the moderate scale for backward compat with existing code
  const projection = projections.moderate;

  // Sprint 6: Fetch pension estimate and net worth summary
  // Sprint 7 (TASK-7.7): Fetch spouse for household stats
  // TASK-7.14: Fetch income sources for confidence band widening
  // TASK-7.15: Fetch prescriptive advice
  const [pensionRes, netWorthRes, spouseRes, sourcesRes, adviceRes, actionPlanRes] = await Promise.all([
    fetch(`${BACKEND_URL}/api/projection/pension-estimate`, { headers }),
    fetch(`${BACKEND_URL}/api/net-worth/summary`, { headers }),
    fetch(`${BACKEND_URL}/api/spouse`, { headers }),
    fetch(`${BACKEND_URL}/api/income-sources`, { headers }),
    fetch(`${BACKEND_URL}/api/projection/advice`, { headers }),
    fetch(`${BACKEND_URL}/api/projection/action-plan`, { headers }),
  ]);

  let rawPension = null;
  let netWorth = null;
  let spouse = null;
  let incomeSources: any[] = [];
  if (pensionRes.ok) rawPension = await pensionRes.json();
  if (netWorthRes.ok) netWorth = await netWorthRes.json();
  if (spouseRes.ok) spouse = await spouseRes.json();
  // 404 means no spouse — that's fine, spouse stays null
  if (sourcesRes.ok) {
    const sourcesData = await sourcesRes.json();
    incomeSources = Array.isArray(sourcesData) ? sourcesData : [];
  }

  // Unwrap combined pension response (TASK-7.7)
  // New shape: { user_pension: {...}, spouse_pension: {...} or null, household_pension_monthly: "..." }
  // For backward compat with existing UI, extract user_pension as pensionEstimate
  const pensionEstimate = rawPension?.user_pension ?? rawPension;
  const spousePension = rawPension?.spouse_pension ?? null;
  const householdPensionMonthly = rawPension?.household_pension_monthly ?? null;

  // TASK-7.15: Parse advice response
  let advice = { advice: [], count: 0 };
  if (adviceRes.ok) advice = await adviceRes.json();

  // TASK-7.17: Parse action plan response
  let actionPlan = { actions: [], count: 0, month: '' };
  if (actionPlanRes.ok) actionPlan = await actionPlanRes.json();

  return {
    projection,
    projections,
    profile,
    pensionEstimate,
    spousePension,
    householdPensionMonthly,
    spouse,
    netWorth,
    incomeSources,
    advice,
    actionPlan,
    error: null
  };
};