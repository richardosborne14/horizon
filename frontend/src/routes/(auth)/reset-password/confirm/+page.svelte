<!--
  Reset password confirm page — /reset-password/confirm?token=xxx

  Shown when the user clicks the reset link from their email.
  New password + confirm password form.
  Token is passed as a hidden field from the server load data.
  Uses i18n keys auth.reset_confirm.*.
-->
<script lang="ts">
	import { t } from 'svelte-i18n';
	import { enhance } from '$app/forms';
	import AuthLayout from '$lib/components/AuthLayout.svelte';
	import type { ActionData, PageData } from './$types';

	/** Token + any server-loaded data */
	export let data: PageData;
	/** Server action return data */
	export let form: ActionData;

	let loading = false;
	let passwordError = '';
	let confirmError = '';

	/**
	 * Client-side validation for the new password fields.
	 */
	function validate(formData: FormData): boolean {
		passwordError = '';
		confirmError = '';

		const password = formData.get('password') as string;
		const confirmPassword = formData.get('confirm_password') as string;

		if (password.length < 8) {
			passwordError = $t('errors.password_too_short');
			return false;
		}
		if (password !== confirmPassword) {
			confirmError = $t('errors.passwords_no_match');
			return false;
		}
		return true;
	}

	function resolveError(message: string): string {
		const codes: Record<string, string> = {
			password_too_short: $t('errors.password_too_short'),
			passwords_no_match: $t('errors.passwords_no_match'),
			invalid_token: $t('auth.reset_confirm.invalid_token'),
			network: $t('errors.network'),
			generic: $t('errors.generic')
		};
		return codes[message] ?? message;
	}
</script>

<svelte:head>
	<title>Nouveau mot de passe — Communauté Coiffure</title>
</svelte:head>

<AuthLayout title={$t('auth.reset_confirm.title')} subtitle={$t('auth.reset_confirm.subtitle')}>
	{#if form?.success}
		<!-- ── Success state ───────────────────────────────────────────────── -->
		<div class="text-center py-4" role="status" aria-live="polite">
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
				{$t('auth.reset_confirm.success_title')}
			</h2>
			<p class="text-sm mb-6" style="color: var(--color-text-muted)">
				{$t('auth.reset_confirm.success_message')}
			</p>

			<a
				href="/login"
				class="btn-primary w-full justify-center"
				data-coco-desc="Lien vers la page de connexion après réinitialisation du mot de passe"
			>
				{$t('auth.reset_confirm.login_link')}
			</a>
		</div>
	{:else}
		<!-- ── Global error (invalid / expired token) ─────────────────────── -->
		{#if form?.message && !form?.field}
			<div
				class="mb-5 px-4 py-3 rounded-lg text-sm"
				role="alert"
				style="background: var(--color-status-error-bg); color: var(--color-status-error)"
			>
				{resolveError(form.message)}
			</div>
		{/if}

		<!-- ── New password form ───────────────────────────────────────────── -->
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
			aria-label={$t('auth.reset_confirm.title')}
		>
			<!-- Hidden token field — value comes from ?token= query param via load function -->
			<input type="hidden" name="token" value={data.token} />

			<!-- New password -->
			<div class="mb-4">
				<label
					for="password"
					class="label"
					data-coco-desc="Champ pour saisir le nouveau mot de passe"
				>
					{$t('auth.reset_confirm.password_label')}
				</label>
				<input
					id="password"
					name="password"
					type="password"
					autocomplete="new-password"
					placeholder={$t('auth.reset_confirm.password_placeholder')}
					class="input"
					class:border-red-400={passwordError || form?.field === 'password'}
					disabled={loading}
					data-coco-desc="Champ nouveau mot de passe - 8 caractères minimum"
					aria-describedby={passwordError ? 'password-error' : undefined}
					aria-invalid={!!passwordError}
				/>
				{#if passwordError}
					<p id="password-error" class="error-msg">{passwordError}</p>
				{:else if form?.field === 'password'}
					<p id="password-error" class="error-msg">{resolveError(form.message)}</p>
				{/if}
			</div>

			<!-- Confirm password -->
			<div class="mb-6">
				<label
					for="confirm_password"
					class="label"
					data-coco-desc="Champ pour confirmer le nouveau mot de passe"
				>
					{$t('auth.reset_confirm.confirm_label')}
				</label>
				<input
					id="confirm_password"
					name="confirm_password"
					type="password"
					autocomplete="new-password"
					placeholder={$t('auth.reset_confirm.confirm_placeholder')}
					class="input"
					class:border-red-400={confirmError || form?.field === 'confirm_password'}
					disabled={loading}
					data-coco-desc="Champ confirmation du nouveau mot de passe"
					aria-describedby={confirmError ? 'confirm-error' : undefined}
					aria-invalid={!!confirmError}
				/>
				{#if confirmError}
					<p id="confirm-error" class="error-msg">{confirmError}</p>
				{:else if form?.field === 'confirm_password'}
					<p id="confirm-error" class="error-msg">{resolveError(form.message)}</p>
				{/if}
			</div>

			<button
				type="submit"
				class="btn-primary w-full"
				disabled={loading}
				data-coco-desc="Bouton pour valider le nouveau mot de passe"
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
					{$t('auth.reset_confirm.submitting')}
				{:else}
					{$t('auth.reset_confirm.submit')}
				{/if}
			</button>
		</form>
	{/if}
</AuthLayout>
