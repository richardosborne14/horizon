<!--
  Qui sommes-nous ? — Public "about" page.

  TASK-2.12.1: Eric supplied the copy in sprint-2.18-eric-fixes/qui sommes nous-1.docx.
  The page lives in (public)/ so no auth is required — footer links from both the
  public landing page and the in-app shell point here without bouncing to /login.

  Layout: narrow reading column (760px max-width), matching the blog article pattern.
  Accordion pattern (click-to-reveal sections) deferred — ship with all sections visible.
  All text via i18n keys (no hardcoded French strings).
  data-coco-desc on all interactive elements.
-->
<script lang="ts">
	import { t } from 'svelte-i18n';

	const SITE_URL = 'https://communaute-coiffure.fr';
	const canonicalUrl = `${SITE_URL}/qui-sommes-nous`;
	const ogImage = `${SITE_URL}/og-default.jpg`;
</script>

<svelte:head>
	<title>{$t('landing.about.page_title')}</title>
	<meta name="description" content={$t('landing.about.meta_description')} />

	<!-- OpenGraph -->
	<meta property="og:title" content={$t('landing.about.page_title')} />
	<meta property="og:description" content={$t('landing.about.meta_description')} />
	<meta property="og:image" content={ogImage} />
	<meta property="og:type" content="website" />
	<meta property="og:url" content={canonicalUrl} />
	<meta property="og:site_name" content="Communauté Coiffure" />

	<!-- Twitter card -->
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content={$t('landing.about.page_title')} />
	<meta name="twitter:description" content={$t('landing.about.meta_description')} />
	<meta name="twitter:image" content={ogImage} />

	<link rel="canonical" href={canonicalUrl} />
</svelte:head>

<main class="about-page" data-coco-desc="Page Qui sommes-nous — présentation de Communauté Coiffure et d'Éric, fondateur">

	<!-- Back link -->
	<nav class="about-page__nav" aria-label="Navigation">
		<a
			href="/"
			class="about-page__back"
			data-coco-desc="Retour à l'accueil Communauté Coiffure"
		>
			← {$t('landing.about.back_to_home')}
		</a>
	</nav>

	<!-- Hero header -->
	<header class="about-page__header">
		<p class="about-page__kicker">{$t('landing.about.kicker')}</p>
		<h1 class="about-page__title">{$t('landing.about.headline')}</h1>
		<p class="about-page__subtitle">{$t('landing.about.subtitle')}</p>
	</header>

	<!-- Section 1: L'histoire d'une conviction -->
	<section class="about-page__section" aria-labelledby="section-histoire">
		<h2 id="section-histoire" class="about-page__section-title">
			{$t('landing.about.section1_title')}
		</h2>
		<p class="about-page__body">{$t('landing.about.section1_p1')}</p>
		<p class="about-page__body">{$t('landing.about.section1_p2')}</p>
		<p class="about-page__body">{$t('landing.about.section1_p3')}</p>
	</section>

	<!-- Section 2: Pourquoi Communauté Coiffure ? -->
	<section class="about-page__section" aria-labelledby="section-pourquoi">
		<h2 id="section-pourquoi" class="about-page__section-title">
			{$t('landing.about.section2_title')}
		</h2>
		<p class="about-page__body">{$t('landing.about.section2_p1')}</p>
		<p class="about-page__body">{$t('landing.about.section2_p2')}</p>
	</section>

	<!-- Section 3: Notre mission — Le pilotage par les chiffres -->
	<section class="about-page__section" aria-labelledby="section-mission">
		<h2 id="section-mission" class="about-page__section-title">
			{$t('landing.about.section3_title')}
		</h2>
		<p class="about-page__body">{$t('landing.about.section3_intro')}</p>
		<ul class="about-page__mission-list">
			<li class="about-page__mission-item">
				<span class="about-page__mission-label">{$t('landing.about.section3_item1_label')}</span>
				{$t('landing.about.section3_item1_body')}
			</li>
			<li class="about-page__mission-item">
				<span class="about-page__mission-label">{$t('landing.about.section3_item2_label')}</span>
				{$t('landing.about.section3_item2_body')}
			</li>
			<li class="about-page__mission-item">
				<span class="about-page__mission-label">{$t('landing.about.section3_item3_label')}</span>
				{$t('landing.about.section3_item3_body')}
			</li>
		</ul>
	</section>

	<!-- Section 4: Demain, ensemble, nous irons plus loin -->
	<section class="about-page__section" aria-labelledby="section-demain">
		<h2 id="section-demain" class="about-page__section-title">
			{$t('landing.about.section4_title')}
		</h2>
		<p class="about-page__body">{$t('landing.about.section4_p1')}</p>
		<p class="about-page__body">{$t('landing.about.section4_p2')}</p>
		<p class="about-page__body">{$t('landing.about.section4_p3')}</p>
	</section>

	<!-- Section 5: Une nouvelle ère pour la profession -->
	<section class="about-page__section" aria-labelledby="section-nouvelle-ere">
		<h2 id="section-nouvelle-ere" class="about-page__section-title">
			{$t('landing.about.section5_title')}
		</h2>
		<p class="about-page__body">{$t('landing.about.section5_p1')}</p>
		<p class="about-page__body">{$t('landing.about.section5_p2')}</p>
	</section>

	<!-- CTA bar -->
	<div class="about-page__cta-bar" data-coco-desc="Invitation à rejoindre Communauté Coiffure depuis la page Qui sommes-nous">
		<p class="about-page__cta-text">{$t('landing.about.cta_text')}</p>
		<div class="about-page__cta-links">
			<a
				href="/register"
				class="about-page__cta-btn about-page__cta-btn--primary"
				data-coco-desc="S'inscrire à Communauté Coiffure depuis la page Qui sommes-nous"
			>
				{$t('landing.about.cta_register')}
			</a>
			<a
				href="/login"
				class="about-page__cta-btn about-page__cta-btn--secondary"
				data-coco-desc="Se connecter à Communauté Coiffure depuis la page Qui sommes-nous"
			>
				{$t('landing.about.cta_login')}
			</a>
		</div>
	</div>

</main>

<style>
	/* @tweak --about-page-max-width: max width for the reading column */
	.about-page {
		max-width: var(--about-page-max-width, 760px);
		margin: 0 auto;
		padding: 2rem 1.5rem 5rem;
	}

	.about-page__nav {
		margin-bottom: 2rem;
	}

	.about-page__back {
		font-size: 0.9rem;
		color: var(--color-primary, #5b6af0);
		text-decoration: none;
		font-weight: 500;
	}

	.about-page__back:hover {
		text-decoration: underline;
	}

	/* Hero header */
	.about-page__header {
		margin-bottom: 3rem;
		padding-bottom: 2rem;
		border-bottom: 2px solid var(--color-border, #e5e7eb);
	}

	.about-page__kicker {
		font-size: 0.8rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--color-primary, #5b6af0);
		margin-bottom: 0.75rem;
	}

	.about-page__title {
		/* WHY font-fraunces: display font for all page titles per DESIGN_GUIDE.md */
		font-family: 'Fraunces', Georgia, serif;
		font-size: 2.5rem;
		font-weight: 700;
		color: var(--color-text-primary, #1a1a2e);
		line-height: 1.2;
		margin-bottom: 1rem;
	}

	.about-page__subtitle {
		font-size: 1.1rem;
		color: var(--color-text-secondary, #555);
		line-height: 1.6;
		font-style: italic;
	}

	/* Sections */
	.about-page__section {
		margin-bottom: 3rem;
	}

	.about-page__section-title {
		font-family: 'Fraunces', Georgia, serif;
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--color-text-primary, #1a1a2e);
		margin-bottom: 1.25rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--color-border, #e5e7eb);
	}

	.about-page__body {
		font-size: 1rem;
		line-height: 1.75;
		color: var(--color-text-secondary, #444);
		margin-bottom: 1.25rem;
	}

	/* Mission list (bullet items with bold label + body) */
	.about-page__mission-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.about-page__mission-item {
		font-size: 1rem;
		line-height: 1.7;
		color: var(--color-text-secondary, #444);
		padding-left: 1rem;
		border-left: 3px solid var(--color-primary, #5b6af0);
	}

	.about-page__mission-label {
		font-weight: 700;
		color: var(--color-text-primary, #1a1a2e);
		margin-right: 0.25rem;
	}

	/* CTA bar */
	.about-page__cta-bar {
		background: color-mix(in srgb, var(--color-primary, #5b6af0) 6%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-primary, #5b6af0) 20%, transparent);
		border-radius: 12px;
		padding: 1.75rem;
		margin-top: 3rem;
		text-align: center;
	}

	.about-page__cta-text {
		font-size: 1rem;
		color: var(--color-text-secondary, #444);
		margin-bottom: 1rem;
		font-weight: 500;
	}

	.about-page__cta-links {
		display: flex;
		gap: 0.75rem;
		justify-content: center;
		flex-wrap: wrap;
	}

	.about-page__cta-btn {
		padding: 0.65rem 1.5rem;
		border-radius: 8px;
		font-size: 0.9rem;
		font-weight: 600;
		text-decoration: none;
		transition: opacity 0.15s;
	}

	.about-page__cta-btn:hover { opacity: 0.85; }

	.about-page__cta-btn--primary {
		background: var(--color-primary, #5b6af0);
		color: #fff;
	}

	.about-page__cta-btn--secondary {
		background: transparent;
		color: var(--color-primary, #5b6af0);
		border: 1.5px solid var(--color-primary, #5b6af0);
	}

	@media (max-width: 640px) {
		.about-page__title {
			font-size: 1.75rem;
		}

		.about-page__subtitle {
			font-size: 1rem;
		}

		.about-page__section-title {
			font-size: 1.25rem;
		}
	}
</style>
