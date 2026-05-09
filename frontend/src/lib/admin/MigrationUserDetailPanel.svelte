<!--
  MigrationUserDetailPanel — TASK-2.17.9

  Slide-in side panel showing full detail for a single imported user:
  - Profile section (Stripe status, subscription, cohort)
  - Legacy pricing audit trail (all LegacyPricingAudit rows)
  - Recent bubble_import_runs

  Used by MigrationDashboard.svelte when the admin clicks "Détail".

  Props:
    userId — UUID string of the user to load (null = panel hidden)
    on:close — dispatched when the panel should close

  WHY side panel (not modal): the admin workflow is "scan table → check detail →
  go back to table". A side panel keeps the table visible and reduces context
  switching.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { t } from 'svelte-i18n';

  export let userId: string | null = null;

  const dispatch = createEventDispatcher<{ close: void }>();

  // ── State ──────────────────────────────────────────────────────────────────
  interface Profile {
    user_id: string;
    email: string;
    name: string;
    import_status: string;
    legacy_pricing_plan: string | null;
    import_source: string | null;
    import_completion_step: string | null;
    last_login_at: string | null;
    last_paid_at: string | null;
    welcome_email_sent_at: string | null;
    bubble_user_id: string | null;
    stripe_customer_id: string | null;
    salon_name: string | null;
    business_type: string | null;
    stripe_subscription_id: string | null;
    stripe_status: string | null;
    plan_name: string | null;
    mrr_eur: number | null;
    current_period_end: string | null;
  }

  interface AuditRow {
    id: string;
    set_at: string;
    plan: string;
    source: string;
    stripe_subscription_id: string | null;
    notes: string | null;
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
  }

  let loading = false;
  let error = '';
  let profile: Profile | null = null;
  let auditRows: AuditRow[] = [];
  let importRuns: ImportRun[] = [];

  // Re-load whenever userId changes
  $: if (userId) {
    loadDetail(userId);
  } else {
    profile = null;
    auditRows = [];
    importRuns = [];
  }

  async function loadDetail(id: string): Promise<void> {
    loading = true;
    error = '';
    try {
      const resp = await fetch(`/api/admin/migration/users/${id}`);
      if (!resp.ok) {
        error = `Erreur ${resp.status}`;
        return;
      }
      const data = await resp.json();
      profile = data.profile;
      auditRows = data.audit_rows ?? [];
      importRuns = data.import_runs ?? [];
    } catch {
      error = 'Erreur réseau';
    } finally {
      loading = false;
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  function formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric'
    });
  }

  function statusBadgeClass(status: string | null): string {
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
    if (['active', 'trialing'].includes(status)) return 'text-green-700 font-semibold';
    if (status === 'past_due') return 'text-amber-700 font-semibold';
    return 'text-red-700';
  }
</script>

<!-- Overlay backdrop -->
{#if userId}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="fixed inset-0 bg-black/30 z-40"
    on:click={() => dispatch('close')}
    data-coco-desc="Fermer le panneau de détail utilisateur"
  ></div>

  <!-- Panel -->
  <aside
    class="fixed right-0 top-0 h-full w-full max-w-xl bg-white z-50 shadow-2xl
           overflow-y-auto flex flex-col"
    aria-label={$t('admin_migration.detail_panel.title')}
    data-coco-desc="Panneau de détail d'un utilisateur importé depuis Bubble"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)] sticky top-0 bg-white z-10">
      <h2 class="text-base font-semibold text-[var(--color-text-primary)]">
        {$t('admin_migration.detail_panel.title')}
      </h2>
      <button
        on:click={() => dispatch('close')}
        class="p-1.5 rounded-lg hover:bg-gray-100 text-[var(--color-text-muted)]"
        data-coco-desc="Fermer le panneau de détail"
        aria-label={$t('common.close')}
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- Content -->
    <div class="flex-1 p-6 space-y-6">
      {#if loading}
        <p class="text-sm text-[var(--color-text-muted)] animate-pulse">
          {$t('admin_migration.detail_panel.loading')}
        </p>
      {:else if error}
        <p class="text-sm text-red-600">{error}</p>
      {:else if profile}

        <!-- ── Profile ──────────────────────────────────────────────────── -->
        <section data-coco-desc="Profil complet de l'utilisateur importé">
          <h3 class="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-3">
            {$t('admin_migration.detail_panel.section_profile')}
          </h3>
          <div class="rounded-xl border border-[var(--color-border)] divide-y divide-[var(--color-border)] text-sm">
            <div class="flex justify-between px-4 py-2.5">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.col_email')}</span>
              <span class="font-medium">{profile.email}</span>
            </div>
            <div class="flex justify-between px-4 py-2.5">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.col_name')}</span>
              <span class="font-medium">{profile.name ?? '—'}</span>
            </div>
            <div class="flex justify-between px-4 py-2.5 items-center">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.col_status')}</span>
              <span class="px-2 py-0.5 rounded-full text-xs font-medium {statusBadgeClass(profile.import_status)}">
                {$t(`admin_migration.status.${profile.import_status}`)}
              </span>
            </div>
            <div class="flex justify-between px-4 py-2.5">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.col_salon')}</span>
              <span>{profile.salon_name ?? '—'}</span>
            </div>
            <div class="flex justify-between px-4 py-2.5">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.col_plan')}</span>
              <span>{profile.legacy_pricing_plan ?? '—'}</span>
            </div>
            <div class="flex justify-between px-4 py-2.5 items-center">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.col_stripe_status')}</span>
              <span class="{stripeStatusClass(profile.stripe_status)}">
                {profile.stripe_status ?? '—'}
              </span>
            </div>
            {#if profile.mrr_eur}
              <div class="flex justify-between px-4 py-2.5">
                <span class="text-[var(--color-text-muted)]">MRR</span>
                <span class="font-semibold tabular-nums">{profile.mrr_eur.toFixed(2)} €/mois</span>
              </div>
            {/if}
            <div class="flex justify-between px-4 py-2.5">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.col_last_login')}</span>
              <span>{formatDate(profile.last_login_at)}</span>
            </div>
            <div class="flex justify-between px-4 py-2.5">
              <span class="text-[var(--color-text-muted)]">{$t('admin_migration.col_welcome_sent')}</span>
              <span>{profile.welcome_email_sent_at ? formatDate(profile.welcome_email_sent_at) : $t('admin_migration.not_sent')}</span>
            </div>
            {#if profile.bubble_user_id}
              <div class="flex justify-between px-4 py-2.5">
                <span class="text-[var(--color-text-muted)]">Bubble ID</span>
                <span class="font-mono text-xs">{profile.bubble_user_id}</span>
              </div>
            {/if}
          </div>
        </section>

        <!-- ── Audit trail ──────────────────────────────────────────────── -->
        <section data-coco-desc="Piste d'audit de la tarification héritée">
          <h3 class="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-3">
            {$t('admin_migration.detail_panel.section_audit')}
          </h3>
          {#if auditRows.length === 0}
            <p class="text-sm text-[var(--color-text-muted)]">{$t('admin_migration.detail_panel.no_audit')}</p>
          {:else}
            <div class="space-y-2">
              {#each auditRows as row}
                <div class="rounded-lg border border-[var(--color-border)] px-4 py-3 text-sm">
                  <div class="flex items-center justify-between">
                    <span class="font-medium">{row.plan}</span>
                    <span class="text-xs text-[var(--color-text-muted)]">{formatDate(row.set_at)}</span>
                  </div>
                  <div class="flex items-center gap-2 mt-1">
                    <span class="text-xs text-[var(--color-text-muted)]">{row.source}</span>
                    {#if row.stripe_subscription_id}
                      <span class="text-xs font-mono text-[var(--color-text-muted)]">{row.stripe_subscription_id}</span>
                    {/if}
                  </div>
                  {#if row.notes}
                    <p class="text-xs text-[var(--color-text-muted)] mt-1 italic">{row.notes}</p>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </section>

        <!-- ── Recent import runs ───────────────────────────────────────── -->
        {#if importRuns.length > 0}
          <section data-coco-desc="Dernières exécutions de scripts d'import Bubble">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-3">
              {$t('admin_migration.detail_panel.section_runs')}
            </h3>
            <div class="space-y-1.5">
              {#each importRuns.slice(0, 5) as run}
                <div class="flex items-center justify-between rounded-lg border border-[var(--color-border)] px-3 py-2 text-xs">
                  <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full {run.finished_at ? 'bg-green-500' : 'bg-amber-400'}"></span>
                    <span class="font-mono">{run.script_name}</span>
                    {#if run.dry_run}
                      <span class="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">dry-run</span>
                    {/if}
                  </div>
                  <div class="text-[var(--color-text-muted)] tabular-nums">
                    +{run.inserted} ~{run.updated} ⚠{run.errored}
                  </div>
                </div>
              {/each}
            </div>
          </section>
        {/if}

      {/if}
    </div>
  </aside>
{/if}
