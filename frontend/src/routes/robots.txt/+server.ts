/**
 * robots.txt — /robots.txt
 *
 * Allows all crawlers on public pages. Disallows the authenticated app shell
 * (search engines would get redirected to login anyway, but explicit is better).
 * References the XML sitemap.
 */

import type { RequestHandler } from './$types';

const SITE_URL = 'https://communaute-coiffure.fr';

export const GET: RequestHandler = () => {
	const content = [
		'User-agent: *',
		'Allow: /',
		'Allow: /blog',
		'Allow: /blog/',
		'Disallow: /dashboard',
		'Disallow: /pilotage',
		'Disallow: /simulation',
		'Disallow: /taxes',
		'Disallow: /prix',
		'Disallow: /calculateurs',
		'Disallow: /mes-economies',
		'Disallow: /fiches-salaire',
		'Disallow: /compta',
		'Disallow: /settings',
		'Disallow: /control-panel',
		'Disallow: /onboarding',
		'',
		`Sitemap: ${SITE_URL}/sitemap.xml`
	].join('\n');

	return new Response(content, {
		headers: {
			'Content-Type': 'text/plain',
			'Cache-Control': 'public, max-age=86400'
		}
	});
};
