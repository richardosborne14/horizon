<!--
  Reset password request page — /reset-password

  Single email field. On success (API always returns 200), shows a success
  confirmation state instead of the form. Uses i18n keys auth.reset_password.*.
-->
<script lang="ts">
	import { t } from 'svelte-i18n';
	import { enhance } from '$app/forms';
	import AuthLayout from '$lib/components/AuthLayout.svelte';
	import type { ActionData } from './$types';

	export let form: ActionData;

	let loading = false;
	let emailError = '';

	/**
	 * Client-side validation for the email field.
	 */
	function validate(formData: FormData): boolean {
		emailError = '';
		const email = (formData.get('email') as string).trim();
		if (!email) {
			emailError = $t('errors.required');
			return false;
		}
		if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
			emailError = $t('errors.email_invalid');
			return false;
		}
		return true;
	}

	function resolveError(message: string): string {
		const codes: Record<string, string> = {
			required: $t('errors.required'),
			email_invalid: $t('errors.email_invalid'),
			network: $t('errors.network'),
			generic: $t('errors.generic')
		};
		return codes[message] ?? message;
	}
</script>

<svelte:head>
	<title>Mot de passe oublié — Communauté Coiffure</title>
</svelte:head>

<AuthLayout title={$t('auth.reset_password.title')} subtitle={$t('auth.reset_password.subtitle')}>
	{#if form?.success}
		<!-- ── Success state ───────────────────────────────────────────────── -->
		<div
			class="text-center py-4"
			role="status"
			aria-live="polite"
		>
			<!-- Checkmark icon -->
			<div
				class="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4"
				style="background: var(--color-status-success-bg)"
				aria-hidden="true"
			>
				<svg
					class="w-7 h-7"
					style="color: var(--color-status-success)"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2.5"
						d="M5 13l4 4L19 7"
					/>
				</svg>
			</div>

			<h2 class="text-lg font-semibold mb-2" style="color: var(--color-text-primary)">
				{$t('auth.reset_password.success_title')}
			</h2>
			<p class="text-sm mb-6" style="color: var(--color-text-muted)">
				{$t('auth.reset_password.success_message')}
			</p>

			<a
				href="/login"
				class="btn-primary w-full justify-center"
				data-coco-desc="Lien pour retourner à la page de connexion"
			>
				{$t('auth.reset_password.back_to_login')}
			</a>
		</div>
	{:else}
		<!-- ── Request form ────────────────────────────────────────────────── -->

		<!-- Global error banner -->
		{#if form?.message && !form?.field}
			<div
				class="mb-5 px-4 py-3 rounded-lg text-sm"
				role="alert"
				style="background: var(--color-status-error-bg); color: var(--color-status-error)"
			>
				{resolveError(form.message)}
			</div>
		{/if}

		<form
			method="POST"
			use:enhance={({ formData, cancel }) => {
				if (!validate(formData)) {
					cancel();
					return;
				}
				loading = true;
				return async ({ update }) => {
					loading = false;
					await update();
				};
			}}
			novalidate
			aria-label={$t('auth.reset_password.title')}
		>
			<div class="mb-6">
				<label
					for="email"
					class="label"
					data-coco-desc="Champ e-mail pour recevoir un lien de réinitialisation du mot de passe"
				>
					{$t('auth.reset_password.email_label')}
				</label>
				<input
					id="email"
					name="email"
					type="email"
					autocomplete="email"
					placeholder={$t('auth.reset_password.email_placeholder')}
					value={form?.email ?? ''}
					class="input"
					class:border-red-400={emailError || form?.field === 'email'}
					disabled={loading}
					data-coco-desc="Champ pour saisir l'adresse e-mail de réinitialisation"
					aria-describedby={emailError ? 'email-error' : undefined}
					aria-invalid={!!emailError}
				/>
				{#if emailError}
					<p id="email-error" class="error-msg">{emailError}</p>
				{:else if form?.field === 'email'}
					<p id="email-error" class="error-msg">{resolveError(form.message)}</p>
				{/if}
			</div>

			<button
				type="submit"
				class="btn-primary w-full"
				disabled={loading}
				data-coco-desc="Bouton pour envoyer le lien de réinitialisation du mot de passe"
			>
				{#if loading}
					<svg
						class="animate-spin w-4 h-4"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						aria-hidden="true"
					>
						<circle
							class="opacity-25"
							cx="12"
							cy="12"
							r="10"
							stroke="currentColor"
							stroke-width="4"
						/>
						<path
							class="opacity-75"
							fill="currentColor"
							d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
						/>
					</svg>
					{$t('auth.reset_password.submitting')}
				{:else}
					{$t('auth.reset_password.submit')}
				{/if}
			</button>
		</form>

		<p class="mt-5 text-center text-sm">
			<a
				href="/login"
				class="font-medium hover:underline"
				style="color: var(--color-brand-gold)"
				data-coco-desc="Lien pour retourner à la page de connexion"
			>
				← {$t('auth.reset_password.back_to_login')}
			</a>
		</p>
	{/if}
</AuthLayout>
