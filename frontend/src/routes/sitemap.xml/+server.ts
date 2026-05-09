/**
 * Sitemap generator — /sitemap.xml
 *
 * Generates a valid XML sitemap including:
 *   - Static priority pages (landing, blog index)
 *   - All published blog articles (fetched from backend at request time)
 *
 * Search engines discover this file via robots.txt.
 * WHY server-side: article list changes over time so we generate on demand
 * rather than baking it into the static build.
 */

import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

const BACKEND_URL = env.BACKEND_URL ?? 'http://backend:8000';
const SITE_URL = 'https://communaute-coiffure.fr';

/** XML-escape a string safe to place in sitemap URLs. */
function escapeXml(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&apos;');
}

export const GET: RequestHandler = async () => {
	// Fetch published articles for dynamic URLs
	let articleUrls: { slug: string; published_at: string | null }[] = [];
	try {
		const res = await fetch(`${BACKEND_URL}/api/blog/?limit=500&published_only=true`);
		if (res.ok) {
			const articles = await res.json();
			articleUrls = articles.map((a: { slug: string; published_at: string | null }) => ({
				slug: a.slug,
				published_at: a.published_at
			}));
		}
	} catch {
		// Non-blocking — sitemap still emits without articles if backend is down
	}

	const today = new Date().toISOString().slice(0, 10);

	const staticUrls = [
		{ loc: SITE_URL, changefreq: 'weekly', priority: '1.0', lastmod: today },
		{ loc: `${SITE_URL}/blog`, changefreq: 'daily', priority: '0.9', lastmod: today },
		{ loc: `${SITE_URL}/register`, changefreq: 'monthly', priority: '0.7', lastmod: today },
		{ loc: `${SITE_URL}/login`, changefreq: 'monthly', priority: '0.5', lastmod: today }
	];

	const articleEntries = articleUrls
		.map((a) => {
			const lastmod = a.published_at ? a.published_at.slice(0, 10) : today;
			return `  <url>
    <loc>${escapeXml(`${SITE_URL}/blog/${a.slug}`)}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>`;
		})
		.join('\n');

	const staticEntries = staticUrls
		.map(
			(u) => `  <url>
    <loc>${escapeXml(u.loc)}</loc>
    <lastmod>${u.lastmod}</lastmod>
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`
		)
		.join('\n');

	const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${staticEntries}
${articleEntries}
</urlset>`;

	return new Response(xml, {
		headers: {
			'Content-Type': 'application/xml',
			'Cache-Control': 'public, max-age=3600'
		}
	});
};
