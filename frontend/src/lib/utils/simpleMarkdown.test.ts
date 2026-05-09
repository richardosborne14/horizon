/**
 * Unit tests for the SimpleMarkdown renderer.
 *
 * The renderer powers static admin-edited prose (services/[id]
 * long_desc_md). These tests lock in:
 *   - Correct HTML structure for the supported markdown subset.
 *   - HTML escaping (no XSS via raw `<script>` tags).
 *   - Link scheme allow-list (no `javascript:` URLs).
 *   - The exact long_desc_md from the Eric/juridique service
 *     produces the expected block structure (TASK-3.8 acceptance).
 */

import { describe, it, expect } from 'vitest';
import { renderMarkdown, escapeHtml, inline } from './simpleMarkdown';

describe('escapeHtml', () => {
	it('escapes the standard HTML special characters', () => {
		expect(escapeHtml('<script>alert("x")</script>')).toBe(
			'&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
		);
		expect(escapeHtml("it's & that")).toBe('it&#39;s &amp; that');
	});
});

describe('inline', () => {
	it('renders bold and italic', () => {
		expect(inline('**bold** and *italic*')).toBe('<strong>bold</strong> and <em>italic</em>');
	});

	it('does not double-match bold inside italic regex', () => {
		expect(inline('**bold**')).toBe('<strong>bold</strong>');
	});

	it('renders allowed link schemes', () => {
		expect(inline('[Site](https://example.com)')).toContain('href="https://example.com"');
		expect(inline('[Mail](mailto:hello@example.com)')).toContain('mailto:hello@example.com');
		expect(inline('[Local](/blog/article)')).toContain('href="/blog/article"');
	});

	it('rejects javascript: URLs', () => {
		// The pattern only allows http(s)/mailto/root paths — bad scheme falls through unchanged.
		const out = inline('[Click](javascript:alert(1))');
		expect(out).not.toContain('href="javascript');
		expect(out).toContain('[Click](javascript:alert(1))');
	});

	it('opens external links in a new tab with secure rel', () => {
		const html = inline('[Calendly](https://calendly.com/eric)');
		expect(html).toContain('target="_blank"');
		expect(html).toContain('rel="noopener noreferrer"');
	});
});

describe('renderMarkdown — block structure', () => {
	it('returns empty string for empty input', () => {
		expect(renderMarkdown('')).toBe('');
	});

	it('renders headings at all three levels', () => {
		const md = '# H1\n\n## H2\n\n### H3';
		const html = renderMarkdown(md);
		expect(html).toContain('<h1>H1</h1>');
		expect(html).toContain('<h2>H2</h2>');
		expect(html).toContain('<h3>H3</h3>');
	});

	it('groups consecutive `- ` lines into a single <ul>', () => {
		const md = '- one\n- two\n- three';
		expect(renderMarkdown(md)).toBe('<ul><li>one</li><li>two</li><li>three</li></ul>');
	});

	it('groups consecutive `1.` lines into a single <ol>', () => {
		const md = '1. one\n2. two';
		expect(renderMarkdown(md)).toBe('<ol><li>one</li><li>two</li></ol>');
	});

	it('separates paragraphs by blank lines', () => {
		const md = 'First paragraph.\n\nSecond paragraph.';
		const html = renderMarkdown(md);
		expect(html).toContain('<p>First paragraph.</p>');
		expect(html).toContain('<p>Second paragraph.</p>');
	});

	it('escapes raw HTML in the source', () => {
		const md = '<script>alert(1)</script>';
		const html = renderMarkdown(md);
		expect(html).not.toContain('<script>');
		expect(html).toContain('&lt;script&gt;');
	});
});

describe('renderMarkdown — TASK-3.8 juridique copy', () => {
	// This is the long_desc_md value from partner-services.json for
	// `conseil_juridique_eric`. Kept short here for readability.
	const sample = `## Comment ça marche

Le juridique fait peur. Chez Communauté Coiffure on a choisi de ne pas te faire jongler entre dix avocats : **tu nous appelles, Eric prend l'appel**.

### Eric répond directement quand…

- Tu hésites entre deux statuts juridiques (AE, EI, EURL, SASU…) — il connaît la coiffure par cœur.
- Tu as une question simple sur le **versement libératoire**.

### Combien ça coûte

L'appel à Eric est **inclus dans ton abonnement Atlas**.`;

	const html = renderMarkdown(sample);

	it('produces the expected block structure', () => {
		expect(html).toContain('<h2>Comment ça marche</h2>');
		expect(html).toContain('<h3>Eric répond directement quand…</h3>');
		expect(html).toContain('<h3>Combien ça coûte</h3>');
	});

	it('renders bold inside paragraphs', () => {
		expect(html).toContain('<strong>tu nous appelles, Eric prend l&#39;appel</strong>');
		expect(html).toContain('<strong>inclus dans ton abonnement Atlas</strong>');
	});

	it('renders the bullet list', () => {
		expect(html).toMatch(
			/<ul><li>Tu hésites entre deux statuts.*<\/li><li>Tu as une question simple.*<\/li><\/ul>/
		);
	});

	it('escapes the apostrophe in "L\'appel"', () => {
		// `escapeHtml` converts ' to &#39; — paragraph text contains it.
		expect(html).toContain('L&#39;appel à Eric');
	});
});
