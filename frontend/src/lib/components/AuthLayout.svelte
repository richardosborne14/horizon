<script lang="ts">
  /**
   * AuthLayout — dark-themed centered layout for login/register/reset-password pages.
   *
   * Props:
   *   title — pre-translated page title string (e.g., $t('auth.login.title'))
   *   subtitle — pre-translated page subtitle string (optional)
   *
   * WHY pre-translated strings, not i18n keys:
   *   `$_()` with dynamic keys (e.g. `$_($titleKey, '')`) in reactive statements
   *   causes Svelte 5 to rewrite `$titleKey` as `store_get(titleKey)`, which
   *   fails because `titleKey` is a plain string prop, not a store.
   *   The fix: parent pages call `$t('key')` (which works) and pass the result
   *   as a plain string prop. AuthLayout just renders the string.
   */
  import { _ } from 'svelte-i18n';

  export let title: string = '';
  export let subtitle: string = '';

  /** Whether a title was provided (controls spacing/layout) */
  $: hasTitle = title !== '';
  $: hasSubtitle = subtitle !== '';
</script>

<div class="min-h-screen bg-zinc-950 flex items-center justify-center px-4 py-12">
  <div class="w-full max-w-sm">
    <!-- Logo / Brand -->
    <div class="text-center mb-8">
      <h1 class="text-2xl font-bold text-teal-400 tracking-tight">
        Horizon
      </h1>
      <p class="text-xs text-zinc-500 mt-1">Moteur patrimonial freelance</p>
    </div>

    <!-- Card wrapper -->
    <div class="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6">
      {#if hasTitle}
        <h2 class="text-lg font-semibold text-zinc-100 mb-1">{title}</h2>
      {/if}
      {#if hasSubtitle}
        <p class="text-xs text-zinc-500 mb-5">{subtitle}</p>
      {:else if hasTitle}
        <div class="mb-5"></div>
      {/if}
      <slot />
    </div>
  </div>
</div>