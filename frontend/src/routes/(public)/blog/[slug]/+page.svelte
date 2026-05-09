<!--
  Public blog article detail — /blog/[slug]

  Full SSR article page with OpenGraph + Twitter card meta + JSON-LD Article schema.
  Body HTML is rendered via {@html} — safe, content is admin-curated + AI-cleaned.
  data-coco-desc on all interactive elements.
-->
<script lang="ts">
	import { t } from 'svelte-i18n';
	import type { PageData } from './$types';
	import type { BlogArticleFull } from './+page.server';

	export let data: PageData;
	$: article = data.article as BlogArticleFull;

	/** Format ISO date to French readable string. */
	function formatDate(iso: string | null): string {
		if (!iso) return '';
		return new Intl.DateTimeFormat('fr-FR', {
			day: 'numeric',
			month: 'long',
			year: 'numeric'
		}).format(new Date(iso));
	}

	const SITE_URL = 'https://communaute-coiffure.fr';

	$: canonicalUrl = `${SITE_URL}/blog/${article.slug}`;
	const ogImage = `${SITE_URL}/og-blog.jpg`;
	$: publishedAt = article.published_at
		? new Date(article.published_at).toISOString()
		: null;

	/** JSON-LD Article schema for Google. */
	$: jsonLd = JSON.stringify({
		'@context': 'https://schema.org',
		'@type': 'Article',
		headline: article.title,
		description: article.excerpt ?? '',
		image: ogImage,
		datePublished: publishedAt,
		author: {
			'@type': 'Organization',
			name: 'Communauté Coiffure'
		},
		publisher: {
			'@type': 'Organization',
			name: 'Communauté Coiffure',
			url: SITE_URL
		},
		url: canonicalUrl
	});

	/** Copy current URL to clipboard. */
	let copied = false;
	async function copyLink() {
		try {
			await navigator.clipboard.writeText(canonicalUrl);
			copied = true;
			setTimeout(() => (copied = false), 2000);
		} catch {
			// Clipboard API unavailable in some browsers
		}
	}
</script>

<svelte:head>
	<title>{article.title} — Communauté Coiffure</title>
	<meta name="description" content={article.excerpt ?? ''} />

	<!-- OpenGraph -->
	<meta property="og:title" content="{article.title} — Communauté Coiffure" />
	<meta property="og:description" content={article.excerpt ?? ''} />
	<meta property="og:image" content={ogImage} />
	<meta property="og:type" content="article" />
	<meta property="og:url" content={canonicalUrl} />
	<meta property="og:site_name" content="Communauté Coiffure" />
	{#if publishedAt}
		<meta property="article:published_time" content={publishedAt} />
	{/if}

	<!-- Twitter card -->
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content="{article.title} — Communauté Coiffure" />
	<meta name="twitter:description" content={article.excerpt ?? ''} />
	<meta name="twitter:image" content={ogImage} />

	<link rel="canonical" href={canonicalUrl} />

	<!-- JSON-LD Article schema -->
	<!-- eslint-disable-next-line svelte/no-at-html-tags -->
	{@html `<script type="application/ld+json">${jsonLd}</script>`}
</svelte:head>

<article
	class="blog-article"
	data-coco-desc="Article de blog : {article.title}"
>
	<!-- Back link -->
	<nav class="blog-article__nav" aria-label="Navigation blog">
		<a
			href="/blog"
			class="blog-article__back"
			data-coco-desc="Retour à la liste des articles du blog"
		>
			{$t('blog.back_to_blog')}
		</a>
	</nav>

	<header class="blog-article__header">
		<!-- Tags -->
		{#if article.tags.length > 0}
			<div class="blog-article__tags" data-coco-desc="Thèmes de l'article">
				{#each article.tags as tag}
					<span class="blog-article__tag">{tag}</span>
				{/each}
			</div>
		{/if}

		<h1 class="blog-article__title">{article.title}</h1>

		<div class="blog-article__meta">
			{#if article.published_at}
				<time
					class="blog-article__date"
					datetime={article.published_at}
					data-coco-desc="Date de publication : {formatDate(article.published_at)}"
				>
					{$t('blog.published_on', { values: { date: formatDate(article.published_at) } })}
				</time>
			{/if}
			</div>

		</header>

	<!-- Article body (HTML from backend — admin-curated and AI-cleaned) -->
	<div
		class="blog-article__body prose"
		data-coco-desc="Corps de l'article : {article.title}"
	>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		{@html article.body_html}
	</div>

	<!-- Footer actions -->
	<footer class="blog-article__footer">
		<!-- Share link -->
		<button
			class="blog-article__share-btn"
			on:click={copyLink}
			data-coco-desc="Bouton pour copier le lien de l'article"
		>
			{copied ? $t('blog.share_copied') : $t('blog.share_copy_link')}
		</button>

		<!-- Ask CoCo: /coco requires auth → unauthenticated users are redirected to login. -->
		<a
			href="/coco"
			class="blog-article__coco-btn"
			data-coco-desc="Poser une question à CoCo sur cet article — connexion requise"
		>
			{$t('blog.ask_coco_article')}
		</a>
	</footer>

	<!-- CTA bar for non-authenticated users -->
	<div class="blog-article__cta-bar" data-coco-desc="Invitation à rejoindre Communauté Coiffure">
		<p class="blog-article__cta-text">
			Vous souhaitez piloter la rentabilité de votre salon ?
		</p>
		<div class="blog-article__cta-links">
			<a
				href="/register"
				class="blog-article__cta-btn blog-article__cta-btn--primary"
				data-coco-desc="S'inscrire gratuitement à Communauté Coiffure"
			>
				{$t('blog.cta_register')}
			</a>
			<a
				href="/login"
				class="blog-article__cta-btn blog-article__cta-btn--secondary"
				data-coco-desc="Se connecter à Communauté Coiffure"
			>
				{$t('blog.cta_login')}
			</a>
		</div>
	</div>

	<!-- Back link (bottom) -->
	<div class="blog-article__back-bottom">
		<a
			href="/blog"
			class="blog-article__back"
			data-coco-desc="Retour à la liste des articles du blog (bas de page)"
		>
			{$t('blog.back_to_blog')}
		</a>
	</div>
</article>

<style>
	/* @tweak --blog-article-max-width: max width for the article reading column */
	.blog-article {
		max-width: var(--blog-article-max-width, 760px);
		margin: 0 auto;
		padding: 2rem 1.5rem 5rem;
	}

	.blog-article__nav {
		margin-bottom: 1.5rem;
	}

	.blog-article__back {
		font-size: 0.9rem;
		color: var(--color-primary, #5b6af0);
		text-decoration: none;
		font-weight: 500;
	}

	.blog-article__back:hover {
		text-decoration: underline;
	}

	/* Header */
	.blog-article__tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
		margin-bottom: 0.75rem;
	}

	.blog-article__tag {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-primary, #5b6af0);
		padding: 0.15rem 0.5rem;
		border-radius: 4px;
		background: color-mix(in srgb, var(--color-primary, #5b6af0) 10%, transparent);
	}

	.blog-article__title {
		font-size: 2rem;
		font-weight: 700;
		color: var(--color-text-primary, #1a1a2e);
		line-height: 1.3;
		margin-bottom: 1rem;
	}

	.blog-article__meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin-bottom: 1.5rem;
	}

	.blog-article__date {
		font-size: 0.85rem;
		color: var(--color-text-muted, #999);
	}

	.blog-article__ai-badge {
		font-size: 0.75rem;
		padding: 0.15rem 0.5rem;
		border-radius: 4px;
		background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
		color: #6b3a0f;
		font-weight: 600;
	}

	.blog-article__hero-img {
		width: 100%;
		height: auto;
		border-radius: 12px;
		margin-bottom: 2rem;
		display: block;
	}

	/* Article body — prose styles */
	.blog-article__body :global(h1),
	.blog-article__body :global(h2),
	.blog-article__body :global(h3),
	.blog-article__body :global(h4) {
		color: var(--color-text-primary, #1a1a2e);
		font-weight: 700;
		margin-top: 2rem;
		margin-bottom: 0.75rem;
		line-height: 1.3;
	}

	.blog-article__body :global(h2) { font-size: 1.5rem; }
	.blog-article__body :global(h3) { font-size: 1.25rem; }
	.blog-article__body :global(h4) { font-size: 1.1rem; }

	.blog-article__body :global(p) {
		font-size: 1rem;
		line-height: 1.75;
		color: var(--color-text-secondary, #444);
		margin-bottom: 1.25rem;
	}

	.blog-article__body :global(ul),
	.blog-article__body :global(ol) {
		padding-left: 1.5rem;
		margin-bottom: 1.25rem;
	}

	/* WHY explicit list-style: Tailwind preflight resets list-style to none.
	   Without this, <ul>/<ol> from the cleaned HTML render with no bullet markers. */
	.blog-article__body :global(ul) { list-style-type: disc; }
	.blog-article__body :global(ol) { list-style-type: decimal; }

	.blog-article__body :global(li) {
		font-size: 1rem;
		line-height: 1.7;
		color: var(--color-text-secondary, #444);
		margin-bottom: 0.375rem;
	}

	.blog-article__body :global(blockquote) {
		border-left: 4px solid var(--color-primary, #5b6af0);
		padding: 0.75rem 1.25rem;
		background: color-mix(in srgb, var(--color-primary, #5b6af0) 6%, transparent);
		border-radius: 0 8px 8px 0;
		margin: 1.5rem 0;
		font-style: italic;
		color: var(--color-text-secondary, #555);
	}

	.blog-article__body :global(a) {
		color: var(--color-primary, #5b6af0);
		text-decoration: underline;
	}

	.blog-article__body :global(strong) {
		font-weight: 700;
		color: var(--color-text-primary, #1a1a2e);
	}

	.blog-article__body :global(table) {
		width: 100%;
		border-collapse: collapse;
		margin-bottom: 1.5rem;
		font-size: 0.9rem;
	}

	.blog-article__body :global(th),
	.blog-article__body :global(td) {
		border: 1px solid var(--color-border, #e5e7eb);
		padding: 0.5rem 0.75rem;
		text-align: left;
	}

	.blog-article__body :global(th) {
		background: var(--color-bg-muted, #f8f9fa);
		font-weight: 600;
	}

	.blog-article__body :global(img) {
		max-width: 100%;
		border-radius: 8px;
		margin: 1rem 0;
		height: auto;
	}

	.blog-article__body :global(code) {
		font-family: monospace;
		font-size: 0.9em;
		background: var(--color-bg-muted, #f0f0f0);
		padding: 0.1em 0.4em;
		border-radius: 4px;
	}

	/* Footer actions */
	.blog-article__footer {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
		align-items: center;
		padding: 2rem 0;
		border-top: 1px solid var(--color-border, #e5e7eb);
		margin-top: 3rem;
	}

	.blog-article__share-btn {
		padding: 0.5rem 1.25rem;
		border-radius: 8px;
		border: 1.5px solid var(--color-border, #ddd);
		background: transparent;
		color: var(--color-text-secondary, #555);
		font-size: 0.875rem;
		font-weight: 500;
		cursor: pointer;
		transition: background 0.15s, color 0.15s;
	}

	.blog-article__share-btn:hover {
		background: var(--color-bg-muted, #f8f9fa);
	}

	.blog-article__coco-btn {
		padding: 0.5rem 1.25rem;
		border-radius: 8px;
		background: var(--color-primary, #5b6af0);
		color: #fff;
		font-size: 0.875rem;
		font-weight: 600;
		text-decoration: none;
		transition: opacity 0.15s;
	}

	.blog-article__coco-btn:hover {
		opacity: 0.87;
	}

	/* CTA bar */
	.blog-article__cta-bar {
		background: color-mix(in srgb, var(--color-primary, #5b6af0) 6%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-primary, #5b6af0) 20%, transparent);
		border-radius: 12px;
		padding: 1.75rem;
		margin-top: 2rem;
		text-align: center;
	}

	.blog-article__cta-text {
		font-size: 1rem;
		color: var(--color-text-secondary, #444);
		margin-bottom: 1rem;
		font-weight: 500;
	}

	.blog-article__cta-links {
		display: flex;
		gap: 0.75rem;
		justify-content: center;
		flex-wrap: wrap;
	}

	.blog-article__cta-btn {
		padding: 0.65rem 1.5rem;
		border-radius: 8px;
		font-size: 0.9rem;
		font-weight: 600;
		text-decoration: none;
		transition: opacity 0.15s;
	}

	.blog-article__cta-btn:hover { opacity: 0.85; }

	.blog-article__cta-btn--primary {
		background: var(--color-primary, #5b6af0);
		color: #fff;
	}

	.blog-article__cta-btn--secondary {
		background: transparent;
		color: var(--color-primary, #5b6af0);
		border: 1.5px solid var(--color-primary, #5b6af0);
	}

	.blog-article__back-bottom {
		margin-top: 2rem;
	}

	@media (max-width: 640px) {
		.blog-article__title {
			font-size: 1.5rem;
		}

		.blog-article__footer {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
