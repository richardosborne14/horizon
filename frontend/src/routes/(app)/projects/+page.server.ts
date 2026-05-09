/**
 * Projects page server loader — fetches projects and profile.
 *
 * Loads all active projects (split client-side into investments/events)
 * and the user profile (for status change simulation fields).
 */
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const SESSION_COOKIE = 'session_token';
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
  const sessionToken = cookies.get(SESSION_COOKIE);
  if (!sessionToken) {
    return { investments: [], events: [], profile: null, investmentCount: 0 };
  }
  const headers = { Cookie: `${SESSION_COOKIE}=${sessionToken}` };

  // Fetch projects and profile in parallel
  const [projectsRes, profileRes] = await Promise.all([
    fetch(`${BACKEND_URL}/api/projects`, { headers }),
    fetch(`${BACKEND_URL}/api/profile`, { headers }),
  ]);

  if (!projectsRes.ok) {
    console.error(`[projects] GET /api/projects returned ${projectsRes.status}`);
    return { investments: [], events: [], profile: null, investmentCount: 0 };
  }
  if (!profileRes.ok) {
    console.error(`[projects] GET /api/profile returned ${profileRes.status}`);
  }

  const projectsData = await projectsRes.json();
  const profileData = profileRes.ok ? await profileRes.json() : null;

  const allProjects = projectsData.projects ?? [];

  return {
    investments: allProjects.filter((p: any) => p.project_type === 'invest'),
    events: allProjects.filter((p: any) => p.project_type === 'event'),
    profile: profileData,
    investmentCount: allProjects.filter((p: any) => p.project_type === 'invest' && p.is_active).length,
  };
};