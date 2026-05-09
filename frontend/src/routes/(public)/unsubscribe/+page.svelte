<!--
  /unsubscribe — Drip email opt-out confirmation page (TASK-2.12.15).

  Reads ?token= from the URL, calls GET /api/unsubscribe, and shows
  the appropriate success / error copy.

  WHY a dedicated page: the API returns JSON; we need HTML with proper
  styling and a link back to the app.

  data-coco-desc: This page is only seen when arriving from an email link.
  CoCo is not surfaced here (no persistent nav / chat bubble).
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { t } from 'svelte-i18n';

  let status: 'loading' | 'success' | 'error' = 'loading';
  let errorMessage = '';

  onMount(async () => {
    const token = $page.url.searchParams.get('token');
    if (!token) {
      status = 'error';
      errorMessage = $t('unsubscribe.error.missing_token');
      return;
    }

    try {
      const resp = await fetch(`/api/unsubscribe?token=${encodeURIComponent(token)}`);
      if (resp.ok) {
        status = 'success';
      } else {
        const data = await resp.json().catch(() => ({}));
        status = 'error';
        errorMessage = data.detail || $t('unsubscribe.error.generic');
      }
    } catch {
      status = 'error';
      errorMessage = $t('unsubscribe.error.generic');
    }
  });
</script>

<svelte:head>
  <title>{$t('unsubscribe.page_title')} — Communauté Coiffure</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div
  class="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4"
  data-coco-desc="Page de désabonnement des emails de conseil"
>
  <div class="max-w-md w-full text-center space-y-6">

    {#if status === 'loading'}
      <div class="animate-pulse">
        <div class="h-8 bg-[var(--color-surface)] rounded w-3/4 mx-auto mb-4"></div>
        <div class="h-4 bg-[var(--color-surface)] rounded w-1/2 mx-auto"></div>
      </div>

    {:else if status === 'success'}
      <!-- Success state -->
      <div class="text-5xl">✅</div>
      <h1 class="text-2xl font-bold text-[var(--color-text)]">
        {$t('unsubscribe.success.title')}
      </h1>
      <p class="text-[var(--color-text-muted)]">
        {$t('unsubscribe.success.body')}
      </p>
      <p class="text-sm text-[var(--color-text-muted)]">
        {$t('unsubscribe.success.resubscribe_hint')}
      </p>
      <a
        href="/parametrage"
        class="inline-block mt-4 px-6 py-3 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:bg-[var(--color-primary-dark)] transition-colors"
      >
        {$t('unsubscribe.success.cta')}
      </a>

    {:else}
      <!-- Error state -->
      <div class="text-5xl">⚠️</div>
      <h1 class="text-2xl font-bold text-[var(--color-text)]">
        {$t('unsubscribe.error.title')}
      </h1>
      <p class="text-[var(--color-text-muted)]">
        {errorMessage || $t('unsubscribe.error.generic')}
      </p>
      <a
        href="/"
        class="inline-block mt-4 px-6 py-3 rounded-lg border border-[var(--color-border)] text-[var(--color-text)] font-medium hover:bg-[var(--color-surface)] transition-colors"
      >
        {$t('unsubscribe.error.cta')}
      </a>
    {/if}

  </div>
</div>
