/**
 * Public blog article detail — server-side load.
 *
 * Fetches a single published article by slug. Returns 404 if not found or
 * if the article is not published (backend already guards this).
 *
 * @returns article — the full article including body_html
 */

import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';

export interface BlogArticleFull {
	id: string;
	slug: string;
	title: string;
	excerpt: string | null;
	body_html: string;
	tags: string[];
	published_at: string | null;
	is_ai_enhanced: boolean;
}

export const load: PageServerLoad = async ({ params }) => {
	const { slug } = params;

	let res: Response;
	try {
		res = await fetch(`${BACKEND_URL}/api/blog/${slug}`);
	} catch (err) {
		console.error('[blog/article] Fetch failed', err);
		throw error(503, 'Service temporairement indisponible');
	}

	if (res.status === 404) {
		throw error(404, 'Article introuvable');
	}

	if (!res.ok) {
		console.error('[blog/article] Backend error', res.status, slug);
		throw error(500, 'Erreur lors du chargement de l\'article');
	}

	const article: BlogArticleFull = await res.json();
	return { article };
};
