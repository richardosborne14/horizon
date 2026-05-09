<!--
  MigrationDashboard — TASK-2.17.9

  Full-featured admin dashboard for the Bubble migration cohort.

  Sections:
  1. Header KPI cards — 4 import_status cohorts + total
  2. Batch email button + confirmation modal
  3. Filter bar — status pills, search, last-activity dropdown
  4. Cohort table — paginated, with per-row "Détail", "Re-sync Stripe", "Email" actions
  5. Import runs collapsible — recent bubble_import_runs
  6. Blog diffs collapsible — AI-cleaned articles pending review

  WHY one component (not split further): the table + filters + modals share tight
  state (selected user, loading flags, filter values). Splitting into sub-components
  would require prop-drilling everything. Keeping it in one file is the lesser evil.
-->
<script lang="ts">
  import { t } from 'svelte-i18n';
  import MigrationUserDetailPanel from './MigrationUserDetailPanel.svelte';

  // ── Types ──────────────────────────────────────────────────────────────────
  interface Summary {
    imported_active_paying: number;
    imported_active_unpaid: number;
    imported_lapsed: number;
    imported_dormant: number;
    total: number;
    last_run_at: string | null;
    blog_articles_cleaned: number;
    blog_articles_pending_review: number;
  }

  interface UserRow {
    user_id: string;
    email: string;
    name: string | null;
    import_status: string;
    legacy_pricing_plan: string | null;
    last_login_at: string | null;
    last_paid_at: string | null;
    welcome_email_sent_at: string | null;
    salon_name: string | null;
    business_type: string | null;
    stripe_subscription_id: string | null;
    stripe_status: string | null;
    mrr_eur: number | null;
    last_reporting_activity_at: string | null;
    days_since_last_activity: number | null;
  }

  interface ImportRun {
    id: string;
    script_name: string;
    started_at: string;
    finished_at: string | null;
    dry_run: boolean;
    inserted: number;
    updated: number;
    skipped: number;
    errored: number;
    in_progress: boolean;
  }

  interface BlogDiff {
    id: string;
    slug: string;
    title: string;
    enhancement_status: string;
    updated_at: string | null;
  }

  // ── Summary ────────────────────────────────────────────────────────────────
  let summary: Summary | null = null;
  let summaryLoading = true;
  let summaryError = '';

  // ── User table ─────────────────────────────────────────────────────────────
  let users: UserRow[] = [];
  let usersTotal = 0;
  let usersPage = 1;
  const PAGE_SIZE = 20;
  let usersLoading = false;
  let usersError = '';

  // Filters
  let filterStatus: string = '';
  let filterActivity: string = '';
  let filterPlan: string = '';
  let filterQ: string = '';
  let qDebounce: ReturnType<typeof setTimeout> | null = null;

  // Detail panel
  let detailUserId: string | null = null;

  // ── Import runs ────────────────────────────────────────────────────────────
  let runs: ImportRun[] = [];
  let runsOpen = false;
  let runsLoading = false;

  // ── Blog diffs ─────────────────────────────────────────────────────────────
  let blogDiffs: BlogDiff[] = [];
  let blogDiffsTotal = 0;
  let blogOpen = false;
  let blogLoading = false;

  // ── Batch email modal ──────────────────────────────────────────────────────
  let batchModalOpen = false;
  let batchStatus = '';
  let batchSize = 50;
  let batchDryRun = false;
  let batchLoading = false;
  let batchResult: { sent: number; skipped_already_sent: number; errors: number } | null = null;

  // ── Row actions ────────────────────────────────────────────────────────────
  let actionLoading: Record<string, string> = {}; // userId → 'email'|'resync'

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  loadSummary();
  loadUsers();

  async function loadSummary(): Promise<void> {
    summaryLoading = true;
    summaryError = '';
    try {
      const resp = await fetch('/api/admin/migration/summary');
      if (!resp.ok) { summaryError = `Erreur ${resp.status}`; return; }
      summary = await resp.json();
    } catch {
      summaryError = 'Erreur réseau';
    } finally {
      summaryLoading = false;
    }
  }

  async function loadUsers(page = 1): Promise<void> {
    usersLoading = true;
    usersError = '';
    usersPage = page;
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (filterStatus) params.set('status', filterStatus);
    if (filterActivity) params.set('last_activity', filterActivity);
    if (filterPlan) params.set('plan', filterPlan);
    if (filterQ) params.set('q', filterQ);

    try {
      const resp = await fetch(`/api/admin/migration/users?${params}`);
      if (!resp.ok) { usersError = `Erreur ${resp.status}`; return; }
      const data = await resp.json();
      users = data.items;
      usersTotal = data.total;
    } catch {
      usersError = 'Erreur réseau';
    } finally {
      usersLoading = false;
    }
  }

  async function loadRuns(): Promise<void> {
    runsLoading = true;
    try {
      const resp = await fetch('/api/admin/migration/runs?limit=15');
      if (resp.ok) runs = await resp.json();
    } finally {
      runsLoading = false;
    }
  }

  async function loadBlogDiffs(): Promise<void> {
    blogLoading = true;
    try {
      const resp = await fetch('/api/admin/migration/blog/diffs?page=1&page_size=30');
      if (resp.ok) {
        const data = await resp.json();
        blogDiffs = data.items;
        blogDiffsTotal = data.total;
      }
    } finally {
      blogLoading = false;
    }
  }

  function handleQInput(): void {
    if (qDebounce) clearTimeout(qDebounce);
    qDebounce = setTimeout(() => loadUsers(1), 350);
  }

  function applyFilter(field: 'status' | 'activity' | 'plan', value: string): void {
    if (field === 'status') filterStatus = filterStatus === value ? '' : value;
    if (field === 'activity') filterActivity = filterActivity === value ? '' : value;
    if (field === 'plan') filterPlan = filterPlan === value ? '' : value;
    loadUsers(1);
  }

  function toggleRuns(): void {
    runsOpen = !runsOpen;
    if (runsOpen && runs.length === 0) loadRuns();
  }

  function toggleBlogDiffs(): void {
    blogOpen = !blogOpen;
    if (blogOpen && blogDiffs.length === 0) loadBlogDiffs();
  }

  // ── Row actions ─────────────────────────────────────────────────────────────

  async function sendWelcomeEmail(userId: string): Promise<void> {
    actionLoading = { ...actionLoading, [userId]: 'email' };
    try {
      const resp = await fetch(`/api/admin/migration/users/${userId}/welcome-email`, { method: 'POST' });
      if (resp.ok) {
        await loadUsers(usersPage);
        await loadSummary();
      }
    } finally {
      const next = { ...actionLoading };
      delete next[userId];
      actionLoading = next;
    }
  }

  async function resyncStripe(userId: string): Promise<void> {
    actionLoading = { ...actionLoading, [userId]: 'resync' };
    try {
      const resp = await fetch(`/api/admin/migration/users/${userId}/resync-stripe`, { method: 'POST' });
      if (resp.ok) await loadUsers(usersPage);
    } finally {
      const next = { ...actionLoading };
      delete next[userId];
      actionLoading = next;
    }
  }

  // ── Batch email ─────────────────────────────────────────────────────────────

  async function sendBatch(): Promise<void> {
    batchLoading = true;
    batchResult = null;
    try {
      const resp = await fetch('/api/admin/migration/cutover-emails/send-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          batch_size: batchSize,
          status_filter: batchStatus || null,
          dry_run: batchDryRun,
        }),
      });
      if (resp.ok) {
        batchResult = await resp.json();
        await loadUsers(usersPage);
        await loadSummary();
      }
    } finally {
      batchLoading = false;
    }
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  function formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function statusBadgeClass(status: string): string {
    switch (status) {
      case 'imported_active_paying': return 'bg-green-100 text-green-800';
      case 'imported_active_unpaid': return 'bg-blue-100 text-blue-800';
      case 'imported_lapsed':        return 'bg-amber-100 text-amber-800';
      case 'imported_dormant':       return 'bg-gray-100 text-gray-600';
      default:                       return 'bg-gray-100 text-gray-500';
    }
  }

  function stripeStatusClass(status: string | null): string {
    if (!status) return 'text-gray-400';
    if (['active', 'trialing'].includes(status)) return 'text-green-700';
    if (status === 'past_due') return 'text-amber-700';
    return 'text-red-600';
  }

  const totalPages = (total: number) => Math.max(1, Math.ceil(total / PAGE_SIZE));
</script>

<!-- Detail panel (teleports to overlay) -->
<MigrationUserDetailPanel
  userId={detailUserId}
  on:close={() => (detailUserId = null)}
/>

<!-- ── KPI Cards ──────────────────────────────────────────────────────────── -->
<div data-coco-desc="Tableau de bord de la migration Bubble vers la nouvelle plateforme">

  {#if summaryError}
    <p class="text-sm text-red-600 mb-4">{summaryError}</p>
  {:else}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {#each [
        { key: 'imported_active_paying', color: 'green' },
        { key: 'imported_active_unpaid', color: 'blue' },
        { key: 'imported_lapsed',        color: 'amber' },
        { key: 'imported_dormant',       color: 'gray'  },
      ] as kpi}
        {@const count = summary ? summary[kpi.key as keyof Summary] as number : 0}
        {@const isActive = filterStatus === kpi.key}
        <button
          class="rounded-xl border p-4 text-left transition-all
            {isActive
              ? 'border-[var(--color-brand-gold)] ring-2 ring-[var(--color-brand-gold)]/20'
              : 'border-[var(--color-border)] hover:border-gray-300'}"
          on:click={() => applyFilter('status', kpi.key)}
          data-coco-desc="Filtrer le tableau par statut {kpi.key}"
          aria-pressed={isActive}
        >
          <div class="text-2xl font-bold tabular-nums text-[var(--color-text-primary)]">
            {summaryLoading ? '…' : count}
          </div>
          <div class="text-xs text-[var(--color-text-muted)] mt-1">
            {$t(`admin_migration.status.${kpi.key}`)}
          </div>
        </button>
      {/each}
    </div>

    <!-- Total + last run -->
    <div class="flex items-center gap-4 text-sm text-[var(--color-text-muted)] mb-6">
      <span>
        <strong class="text-[var(--color-text-primary)]">{summary?.total ?? 0}</strong>
        {$t('admin_migration.summary.total_imported')}
      </span>
      {#if summary?.last_run_at}
        <span>·</span>
        <span>{$t('admin_migration.summary.last_run')} {formatDate(summary.last_run_at)}</span>
      {/if}
      {#if summary && summary.blog_articles_pending_review > 0}
        <span>·</span>
        <span class="text-amber-700">
          {summary.blog_articles_pending_review} {$t('admin_migration.summary.blog_pending')}
        </span>
      {/if}
    </div>
  {/if}

  <!-- ── Batch email button ──────────────────────────────────────────────────── -->
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-base font-semibold text-[var(--color-text-primary)]">
      {$t('admin_migration.users_table.title')}
    </h2>
    <div class="flex gap-2">
      <a
        href="/api/admin/migration/users.csv"
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-[var(--color-border)]
               text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
        data-coco-desc="Télécharger l'export CSV des utilisateurs importés"
        download
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
        </svg>
        CSV
      </a>
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg
               bg-[var(--color-brand-gold)] text-white hover:opacity-90 transition-opacity"
        on:click={() => (batchModalOpen = true)}
        data-coco-desc="Ouvrir le dialogue d'envoi en lot des emails de bienvenue"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>
        {$t('admin_migration.batch_email.btn')}
      </button>
    </div>
  </div>

  <!-- ── Filter bar ──────────────────────────────────────────────────────────── -->
  <div class="flex flex-wrap items-center gap-2 mb-4" data-coco-desc="Filtres de la liste des utilisateurs importés">
    <!-- Status pills -->
    {#each ['imported_active_paying', 'imported_active_unpaid', 'imported_lapsed', 'imported_dormant'] as s}
      <button
        class="px-3 py-1 text-xs rounded-full border transition-colors
          {filterStatus === s
            ? 'border-[var(--color-brand-gold)] bg-[var(--color-brand-gold)]/10 text-[var(--color-brand-gold)]'
            : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-gray-400'}"
        on:click={() => applyFilter('status', s)}
        data-coco-desc="Filtrer par statut {s}"
        aria-pressed={filterStatus === s}
      >
        {$t(`admin_migration.status.${s}_short`)}
      </button>
    {/each}

    <!-- Activity filter -->
    <select
      bind:value={filterActivity}
      on:change={() => loadUsers(1)}
      class="text-xs border border-[var(--color-border)] rounded-lg px-2 py-1 text-[var(--color-text-muted)]"
      data-coco-desc="Filtrer par dernière activité"
    >
      <option value="">{$t('admin_migration.filter.all_activity')}</option>
      <option value="7d">{$t('admin_migration.filter.activity_7d')}</option>
      <option value="30d">{$t('admin_migration.filter.activity_30d')}</option>
      <option value="90d">{$t('admin_migration.filter.activity_90d')}</option>
      <option value="never">{$t('admin_migration.filter.activity_never')}</option>
    </select>

    <!-- Search -->
    <div class="flex-1 min-w-48">
      <input
        type="search"
        bind:value={filterQ}
        on:input={handleQInput}
        placeholder={$t('admin_migration.filter.search_placeholder')}
        class="w-full text-sm border border-[var(--color-border)] rounded-lg px-3 py-1.5
               focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-gold)]/30"
        data-coco-desc="Rechercher par email ou nom dans la liste des utilisateurs importés"
      />
    </div>

    {#if filterStatus || filterActivity || filterQ}
      <button
        class="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
        on:click={() => { filterStatus = ''; filterActivity = ''; filterQ = ''; loadUsers(1); }}
        data-coco-desc="Effacer tous les filtres actifs"
      >
        {$t('admin_migration.filter.clear')}
      </button>
    {/if}
  </div>

  <!-- ── User table ──────────────────────────────────────────────────────────── -->
  <div class="rounded-xl border border-[var(--color-border)] overflow-hidden mb-4"
       data-coco-desc="Tableau des utilisateurs importés depuis Bubble">
    {#if usersLoading}
      <div class="p-8 text-center text-sm text-[var(--color-text-muted)] animate-pulse">
        {$t('admin_migration.users_table.loading')}
      </div>
    {:else if usersError}
      <div class="p-8 text-center text-sm text-red-600">{usersError}</div>
    {:else if users.length === 0}
      <div class="p-8 text-center text-sm text-[var(--color-text-muted)]">
        {$t('admin_migration.users_table.empty')}
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 border-b border-[var(--color-border)]">
            <tr>
              <th class="px-4 py-3 text-left font-medium text-[var(--color-text-muted)]">
                {$t('admin_migration.col_email')}
              </th>
              <th class="px-4 py-3 text-left font-medium text-[var(--color-text-muted)]">
                {$t('admin_migration.col_salon')}
              </th>
              <th class="px-4 py-3 text-left font-medium text-[var(--color-text-muted)]">
                {$t('admin_migration.col_status')}
              </th>
              <th class="px-4 py-3 text-left font-medium text-[var(--color-text-muted)]">
                {$t('admin_migration.col_stripe_status')}
              </th>
              <th class="px-4 py-3 text-right font-medium text-[var(--color-text-muted)]">
                MRR
              </th>
              <th class="px-4 py-3 text-left font-medium text-[var(--color-text-muted)]">
                {$t('admin_migration.col_last_activity')}
              </th>
              <th class="px-4 py-3 text-left font-medium text-[var(--color-text-muted)]">
                {$t('admin_migration.col_welcome_sent')}
              </th>
              <th class="px-4 py-3 text-right font-medium text-[var(--color-text-muted)]">
                {$t('admin_migration.col_actions')}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--color-border)]">
            {#each users as user}
              <tr class="hover:bg-gray-50">
                <td class="px-4 py-3">
                  <div class="font-medium truncate max-w-48">{user.email}</div>
                  {#if user.name}
                    <div class="text-xs text-[var(--color-text-muted)]">{user.name}</div>
                  {/if}
                </td>
                <td class="px-4 py-3 text-[var(--color-text-muted)]">
                  {user.salon_name ?? '—'}
                </td>
                <td class="px-4 py-3">
                  <span class="px-2 py-0.5 rounded-full text-xs font-medium {statusBadgeClass(user.import_status)}">
                    {$t(`admin_migration.status.${user.import_status}_short`)}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <span class="text-xs {stripeStatusClass(user.stripe_status)}">
                    {user.stripe_status ?? '—'}
                  </span>
                </td>
                <td class="px-4 py-3 text-right tabular-nums text-xs">
                  {user.mrr_eur != null ? user.mrr_eur.toFixed(2) + ' €' : '—'}
                </td>
                <td class="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                  {#if user.days_since_last_activity != null}
                    <span class="{user.days_since_last_activity > 90 ? 'text-red-600' : ''}">
                      {user.days_since_last_activity} j
                    </span>
                  {:else}
                    <span class="text-red-600">jamais</span>
                  {/if}
                </td>
                <td class="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                  {#if user.welcome_email_sent_at}
                    <span class="text-green-700">✓ {formatDate(user.welcome_email_sent_at)}</span>
                  {:else}
                    <span>—</span>
                  {/if}
                </td>
                <td class="px-4 py-3">
                  <div class="flex items-center justify-end gap-1">
                    <button
                      class="px-2 py-1 text-xs rounded border border-[var(--color-border)]
                             text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]
                             hover:border-gray-400 transition-colors"
                      on:click={() => (detailUserId = user.user_id)}
                      data-coco-desc="Afficher le détail complet de l'utilisateur {user.email}"
                    >
                      {$t('admin_migration.action.detail')}
                    </button>
                    <button
                      class="px-2 py-1 text-xs rounded border border-[var(--color-border)]
                             text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]
                             hover:border-gray-400 transition-colors disabled:opacity-40"
                      on:click={() => resyncStripe(user.user_id)}
                      disabled={actionLoading[user.user_id] === 'resync'}
                      data-coco-desc="Re-synchroniser le statut Stripe de l'utilisateur {user.email}"
                    >
                      {actionLoading[user.user_id] === 'resync' ? '…' : $t('admin_migration.action.resync')}
                    </button>
                    <button
                      class="px-2 py-1 text-xs rounded border border-[var(--color-border)]
                             text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]
                             hover:border-gray-400 transition-colors disabled:opacity-40
                             {user.welcome_email_sent_at ? 'opacity-40' : ''}"
                      on:click={() => sendWelcomeEmail(user.user_id)}
                      disabled={actionLoading[user.user_id] === 'email' || !!user.welcome_email_sent_at}
                      data-coco-desc="Envoyer l'email de bienvenue à l'utilisateur {user.email}"
                    >
                      {actionLoading[user.user_id] === 'email' ? '…' : $t('admin_migration.action.email')}
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      {#if usersTotal > PAGE_SIZE}
        <div class="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)] text-sm">
          <span class="text-[var(--color-text-muted)]">
            {(usersPage - 1) * PAGE_SIZE + 1}–{Math.min(usersPage * PAGE_SIZE, usersTotal)}
            / {usersTotal}
          </span>
          <div class="flex gap-1">
            <button
              class="px-3 py-1 rounded border border-[var(--color-border)] disabled:opacity-40"
              disabled={usersPage <= 1}
              on:click={() => loadUsers(usersPage - 1)}
              data-coco-desc="Page précédente"
            >
              ‹
            </button>
            <button
              class="px-3 py-1 rounded border border-[var(--color-border)] disabled:opacity-40"
              disabled={usersPage >= totalPages(usersTotal)}
              on:click={() => loadUsers(usersPage + 1)}
              data-coco-desc="Page suivante"
            >
              ›
            </button>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- ── Import runs collapsible ────────────────────────────────────────────── -->
  <div class="rounded-xl border border-[var(--color-border)] mb-4">
    <button
      class="w-full flex items-center justify-between px-4 py-3 text-sm font-medium
             text-[var(--color-text-primary)] hover:bg-gray-50 transition-colors rounded-xl"
      on:click={toggleRuns}
      data-coco-desc="Afficher ou masquer l'historique des scripts d'import Bubble"
      aria-expanded={runsOpen}
    >
      <span>{$t('admin_migration.runs.title')}</span>
      <svg class="w-4 h-4 transition-transform {runsOpen ? 'rotate-180' : ''}"
           fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
      </svg>
    </button>
    {#if runsOpen}
      <div class="border-t border-[var(--color-border)] px-4 py-3">
        {#if runsLoading}
          <p class="text-sm text-[var(--color-text-muted)] animate-pulse">{$t('admin_migration.runs.loading')}</p>
        {:else if runs.length === 0}
          <p class="text-sm text-[var(--color-text-muted)]">{$t('admin_migration.runs.empty')}</p>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="text-[var(--color-text-muted)]">
                  <th class="text-left py-1.5 pr-4">Script</th>
                  <th class="text-left py-1.5 pr-4">Démarré</th>
                  <th class="text-left py-1.5 pr-4">Statut</th>
                  <th class="text-right py-1.5 pr-4">+Ins</th>
                  <th class="text-right py-1.5 pr-4">~Upd</th>
                  <th class="text-right py-1.5">⚠Err</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[var(--color-border)]">
                {#each runs as run}
                  <tr>
                    <td class="py-1.5 pr-4 font-mono">{run.script_name}</td>
                    <td class="py-1.5 pr-4 text-[var(--color-text-muted)]">{formatDate(run.started_at)}</td>
                    <td class="py-1.5 pr-4">
                      {#if run.in_progress}
                        <span class="text-amber-600">En cours</span>
                      {:else if run.dry_run}
                        <span class="text-gray-500">dry-run</span>
                      {:else}
                        <span class="text-green-700">Terminé</span>
                      {/if}
                    </td>
                    <td class="py-1.5 pr-4 text-right tabular-nums text-green-700">{run.inserted}</td>
                    <td class="py-1.5 pr-4 text-right tabular-nums text-blue-700">{run.updated}</td>
                    <td class="py-1.5 text-right tabular-nums {run.errored > 0 ? 'text-red-600' : 'text-[var(--color-text-muted)]'}">
                      {run.errored}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    {/if}
  </div>

  <!-- ── Blog diffs collapsible ─────────────────────────────────────────────── -->
  <div class="rounded-xl border border-[var(--color-border)] mb-4">
    <button
      class="w-full flex items-center justify-between px-4 py-3 text-sm font-medium
             text-[var(--color-text-primary)] hover:bg-gray-50 transition-colors rounded-xl"
      on:click={toggleBlogDiffs}
      data-coco-desc="Afficher ou masquer les articles blog nettoyés par l'IA en attente de validation"
      aria-expanded={blogOpen}
    >
      <span>
        {$t('admin_migration.blog_diffs.title')}
        {#if summary && summary.blog_articles_pending_review > 0}
          <span class="ml-2 px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-800">
            {summary.blog_articles_pending_review}
          </span>
        {/if}
      </span>
      <svg class="w-4 h-4 transition-transform {blogOpen ? 'rotate-180' : ''}"
           fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
      </svg>
    </button>
    {#if blogOpen}
      <div class="border-t border-[var(--color-border)] px-4 py-3">
        {#if blogLoading}
          <p class="text-sm text-[var(--color-text-muted)] animate-pulse">{$t('admin_migration.blog_diffs.loading')}</p>
        {:else if blogDiffs.length === 0}
          <p class="text-sm text-[var(--color-text-muted)]">{$t('admin_migration.blog_diffs.empty')}</p>
        {:else}
          <p class="text-xs text-[var(--color-text-muted)] mb-3">
            {$t('admin_migration.blog_diffs.note')}
          </p>
          <div class="space-y-2">
            {#each blogDiffs as article}
              <div class="flex items-center justify-between rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
                <div>
                  <span class="font-medium">{article.title}</span>
                  <span class="ml-2 text-xs text-[var(--color-text-muted)] font-mono">{article.slug}</span>
                </div>
                <a
                  href="/admin/blog/articles/{article.id}/diff"
                  class="text-xs text-[var(--color-brand-gold)] hover:underline"
                  data-coco-desc="Voir le diff IA pour l'article {article.title}"
                >
                  {$t('admin_migration.blog_diffs.view_diff')}
                </a>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>

</div>

<!-- ── Batch email modal ──────────────────────────────────────────────────────── -->
{#if batchModalOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
    on:click|self={() => (batchModalOpen = false)}
    data-coco-desc="Dialogue d'envoi en lot des emails de bienvenue"
  >
    <div
      class="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="batch-modal-title"
    >
      <h3 id="batch-modal-title" class="text-base font-semibold text-[var(--color-text-primary)] mb-4">
        {$t('admin_migration.batch_email.modal_title')}
      </h3>

      {#if batchResult}
        <!-- Result state -->
        <div class="rounded-xl border border-[var(--color-border)] p-4 mb-4 text-sm space-y-1.5">
          <div class="flex justify-between">
            <span class="text-[var(--color-text-muted)]">{$t('admin_migration.batch_email.result_sent')}</span>
            <span class="font-semibold text-green-700">{batchResult.sent}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[var(--color-text-muted)]">{$t('admin_migration.batch_email.result_skipped')}</span>
            <span class="font-semibold">{batchResult.skipped_already_sent}</span>
          </div>
          {#if batchResult.errors > 0}
            <div class="flex justify-between">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.batch_email.result_errors')}</span>
              <span class="font-semibold text-red-600">{batchResult.errors}</span>
            </div>
          {/if}
        </div>
        <button
          class="w-full py-2 rounded-xl border border-[var(--color-border)] text-sm"
          on:click={() => { batchModalOpen = false; batchResult = null; }}
          data-coco-desc="Fermer le dialogue de résultat d'envoi en lot"
        >
          {$t('common.close')}
        </button>
      {:else}
        <!-- Config state -->
        <div class="space-y-4 mb-6 text-sm">
          <div>
            <label class="block text-[var(--color-text-muted)] mb-1.5" for="batch-status">
              {$t('admin_migration.batch_email.status_label')}
            </label>
            <select
              id="batch-status"
              bind:value={batchStatus}
              class="w-full border border-[var(--color-border)] rounded-lg px-3 py-2"
              data-coco-desc="Filtrer les destinataires par statut d'import"
            >
              <option value="">{$t('admin_migration.batch_email.all_statuses')}</option>
              <option value="imported_active_paying">{$t('admin_migration.status.imported_active_paying')}</option>
              <option value="imported_active_unpaid">{$t('admin_migration.status.imported_active_unpaid')}</option>
              <option value="imported_lapsed">{$t('admin_migration.status.imported_lapsed')}</option>
              <option value="imported_dormant">{$t('admin_migration.status.imported_dormant')}</option>
            </select>
          </div>
          <div>
            <label class="block text-[var(--color-text-muted)] mb-1.5" for="batch-size">
              {$t('admin_migration.batch_email.size_label')}
            </label>
            <input
              id="batch-size"
              type="number"
              bind:value={batchSize}
              min="1" max="500"
              class="w-full border border-[var(--color-border)] rounded-lg px-3 py-2"
              data-coco-desc="Nombre maximum d'emails à envoyer dans ce lot"
            />
          </div>
          <label class="flex items-center gap-2 cursor-pointer"
                 data-coco-desc="Activer le mode simulation sans envoi réel">
            <input type="checkbox" bind:checked={batchDryRun} class="rounded" />
            <span class="text-[var(--color-text-muted)]">{$t('admin_migration.batch_email.dry_run_label')}</span>
          </label>
          {#if batchDryRun}
            <p class="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
              {$t('admin_migration.batch_email.dry_run_note')}
            </p>
          {/if}
        </div>

        <div class="flex gap-2">
          <button
            class="flex-1 py-2 rounded-xl border border-[var(--color-border)] text-sm text-[var(--color-text-muted)]"
            on:click={() => (batchModalOpen = false)}
            data-coco-desc="Annuler l'envoi en lot"
          >
            {$t('common.cancel')}
          </button>
          <button
            class="flex-1 py-2 rounded-xl bg-[var(--color-brand-gold)] text-white text-sm
                   font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
            on:click={sendBatch}
            disabled={batchLoading}
            data-coco-desc="Confirmer et envoyer les emails de bienvenue en lot"
          >
            {batchLoading ? '…' : batchDryRun ? $t('admin_migration.batch_email.simulate_btn') : $t('admin_migration.batch_email.send_btn')}
          </button>
        </div>
      {/if}
    </div>
  </div>
{/if}
