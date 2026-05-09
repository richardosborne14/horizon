/**
 * Minimal, dependency-free markdown → HTML renderer.
 *
 * Used by SimpleMarkdown.svelte to render admin-edited prose
 * (services/[id] long_desc_md, future static CMS-style content).
 *
 * Supports a small subset:
 *   - `# H1`, `## H2`, `### H3` → headings
 *   - `**bold**` → <strong>
 *   - `*italic*` → <em>
 *   - `- item` lists → <ul><li>
 *   - `1. item` numbered lists → <ol><li>
 *   - Blank-line separated paragraphs
 *   - `[label](url)` links → <a target="_blank" rel="noopener">
 *
 * WHY a custom renderer instead of `marked` / `remark`:
 *   - The .clinerules forbids new deps without discussion.
 *   - We only need this for static admin-edited content; blog
 *     articles store HTML directly so they don't go through here.
 *
 * Security:
 *   - `escapeHtml` runs first so any malicious `<script>` in the
 *     source becomes literal text. Only the safe substitutions
 *     above add HTML back in.
 *   - Link URLs are restricted to `http(s)`, `mailto:`, or root
 *     `/path` references — preventing `javascript:` injection.
 */

/**
 * HTML-escape every special character so the source can never inject
 * arbitrary HTML before our own substitutions add the safe subset back.
 */
export function escapeHtml(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
}

/**
 * Apply inline transforms (links, bold, italic) to a single line of text.
 *
 * Called AFTER the line has been HTML-escaped.
 *
 * @param line - HTML-escaped text fragment.
 * @returns Same line with inline markdown turned into safe HTML.
 */
export function inline(line: string): string {
	// Links [label](url) — must run before bold/italic so the URL doesn't
	// get partially matched by `*…*`. Restrict scheme to http(s), mailto,
	// or absolute root paths to prevent `javascript:` URL injection.
	line = line.replace(
		/\[([^\]]+)\]\((https?:\/\/[^\s)]+|mailto:[^\s)]+|\/[^\s)]*)\)/g,
		'<a href="$2" target="_blank" rel="noopener noreferrer" class="underline">$1</a>'
	);
	// Bold **text**
	line = line.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
	// Italic *text* (run after bold so we don't double-match)
	line = line.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>');
	return line;
}

/**
 * Render a markdown string to safe HTML.
 *
 * Splits the source into block-level groups (headings, lists, paragraphs)
 * separated by blank lines. The output is a string of HTML fragments
 * concatenated together, ready to inject via Svelte `{@html}`.
 *
 * @param md - Raw markdown source. Empty string is allowed.
 * @returns HTML fragment string. Always safe (no scripts, no unknown tags).
 */
export function renderMarkdown(md: string): string {
	if (!md) return '';
	const escaped = escapeHtml(md);
	const lines = escaped.split('\n');
	const out: string[] = [];

	let i = 0;
	while (i < lines.length) {
		const line = lines[i];

		// Heading
		const h = line.match(/^(#{1,3})\s+(.*)$/);
		if (h) {
			const level = h[1].length;
			out.push(`<h${level}>${inline(h[2])}</h${level}>`);
			i++;
			continue;
		}

		// Bulleted list (consecutive `- ` lines)
		if (/^-\s+/.test(line)) {
			const items: string[] = [];
			while (i < lines.length && /^-\s+/.test(lines[i])) {
				items.push(`<li>${inline(lines[i].replace(/^-\s+/, ''))}</li>`);
				i++;
			}
			out.push(`<ul>${items.join('')}</ul>`);
			continue;
		}

		// Numbered list (consecutive `1. `, `2. ` lines)
		if (/^\d+\.\s+/.test(line)) {
			const items: string[] = [];
			while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
				items.push(`<li>${inline(lines[i].replace(/^\d+\.\s+/, ''))}</li>`);
				i++;
			}
			out.push(`<ol>${items.join('')}</ol>`);
			continue;
		}

		// Blank line — skip (paragraph separator)
		if (line.trim() === '') {
			i++;
			continue;
		}

		// Paragraph: gather consecutive non-blank, non-special lines
		const para: string[] = [];
		while (
			i < lines.length &&
			lines[i].trim() !== '' &&
			!/^(#{1,3}\s|-\s|\d+\.\s)/.test(lines[i])
		) {
			para.push(inline(lines[i]));
			i++;
		}
		if (para.length) {
			out.push(`<p>${para.join(' ')}</p>`);
		}
	}

	return out.join('\n');
}
