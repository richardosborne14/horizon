/**
 * Life page server loader — fetches life entities and recurring expenses.
 * Groups entities by type for the template.
 */
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const SESSION_COOKIE = 'session_token';
const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
  const sessionToken = cookies.get(SESSION_COOKIE);
  if (!sessionToken) {
    return { kids: [], pets: [], cars: [], tech: [], recurring: [] };
  }
  const headers = { Cookie: `${SESSION_COOKIE}=${sessionToken}` };

  const [entitiesRes, recurringRes] = await Promise.all([
    fetch(`${BACKEND_URL}/api/life-entities`, { headers }),
    fetch(`${BACKEND_URL}/api/recurring-expenses`, { headers }),
  ]);

  if (!entitiesRes.ok) {
    console.error(`[life] GET /api/life-entities returned ${entitiesRes.status}`);
    return { kids: [], pets: [], cars: [], tech: [], recurring: [] };
  }
  if (!recurringRes.ok) {
    console.error(`[life] GET /api/recurring-expenses returned ${recurringRes.status}`);
  }

  const entitiesData = await entitiesRes.json();
  const recurringData = recurringRes.ok ? await recurringRes.json() : { expenses: [], total: 0 };

  const allEntities = entitiesData.entities ?? [];

  return {
    kids: allEntities.filter((e: any) => e.entity_type === 'kid' && e.is_active),
    pets: allEntities.filter((e: any) => e.entity_type === 'pet' && e.is_active),
    cars: allEntities.filter((e: any) => e.entity_type === 'car' && e.is_active),
    tech: allEntities.filter((e: any) => e.entity_type === 'tech' && e.is_active),
    recurring: recurringData.expenses ?? [],
  };
};