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

  // Fetch initial projection
  const res = await fetch(
    `${BACKEND_URL}/api/projection?scale=${profile?.world_scale || 'moderate'}`,
    { headers }
  );

  if (!res.ok) {
    console.error(`[runway] GET /api/projection returned ${res.status}`);
    return {
      projection: null,
      profile,
      error: res.status === 404 ? 'no_profile' : res.status === 422 ? 'no_birthdate' : 'api_error'
    };
  }

  const projection = await res.json();

  return {
    projection,
    profile,
    error: null
  };
};