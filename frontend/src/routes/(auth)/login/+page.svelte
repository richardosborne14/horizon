<!--
  Login page — /login

  Email + password form. On success, the server action redirects to /dashboard.
  On failure, the `form` prop contains the error message to display.

  All text comes from i18n keys (fr.json → auth.login.*)
  All interactive elements have data-coco-desc for the CoCo AI context system.
-->
<script lang="ts">
	import { t } from 'svelte-i18n';
	import { enhance } from '$app/forms';
	import AuthLayout from '$lib/components/AuthLayout.svelte';
	import type { ActionData } from './$types';

	/** Server action return data (errors or null on fresh load) */
	export let form: ActionData;

	/** Controls the loading spinner during form submission */
	let loading = false;

	/** Client-side field validation errors */
	let emailError = '';
	let passwordError = '';

	/**
	 * Run client-side validation before submitting.
	 * Returns false to cancel submission if validation fails.
	 */
	function validate(formData: FormData): boolean {
		emailError = '';
		passwordError = '';

		const email = (formData.get('email') as string).trim();
		const password = formData.get('password') as string;

		// Email: required + basic format check
		if (!email) {
			emailError = $t('errors.required');
			return false;
		}
		if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
			emailError = $t('errors.email_invalid');
			return false;
		}

		// Password: required
		if (!password) {
			passwordError = $t('errors.required');
			return false;
		}

		return true;
	}

	/**
	 * Resolve an API error message code to a localised string.
	 * Falls back to the raw message if it's not a known code.
	 */
	function resolveError(message: string): string {
		const knownCodes: Record<string, string> = {
			required: $t('errors.required'),
			network: $t('errors.network'),
			generic: $t('errors.generic')
		};
		// Check i18n keys first, else return the raw backend message
		return knownCodes[message] ?? message;
	}
</script>

<svelte:head>
	<title>Connexion — Communauté Coiffure</title>
</svelte:head>

<AuthLayout title={$t('auth.login.title')} subtitle={$t('auth.login.subtitle')}>
	<!-- Global API error banner (shown only when the server action returns a non-field error) -->
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
			// Run client-side validation; cancel the server request if invalid
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
		aria-label={$t('auth.login.title')}
	>
		<!-- Email field -->
		<div class="mb-4">
			<label for="email" class="label" data-coco-desc="Champ pour saisir l'adresse e-mail">
				{$t('auth.login.email_label')}
			</label>
			<input
				id="email"
				name="email"
				type="email"
				autocomplete="email"
				placeholder={$t('auth.login.email_placeholder')}
				value={form?.email ?? ''}
				class="input"
				class:border-red-400={emailError || (form?.field === 'email')}
				disabled={loading}
				data-coco-desc="Champ e-mail pour se connecter"
				aria-describedby={emailError ? 'email-error' : undefined}
				aria-invalid={!!emailError}
			/>
			{#if emailError}
				<p id="email-error" class="error-msg">{emailError}</p>
			{:else if form?.field === 'email'}
				<p id="email-error" class="error-msg">{resolveError(form.message)}</p>
			{/if}
		</div>

		<!-- Password field -->
		<div class="mb-6">
			<div class="flex items-center justify-between mb-1.5">
				<label for="password" class="label mb-0" data-coco-desc="Champ pour saisir le mot de passe">
					{$t('auth.login.password_label')}
				</label>
				<a
					href="/reset-password"
					class="text-xs font-medium hover:underline"
					style="color: var(--color-brand-gold)"
					data-coco-desc="Lien pour réinitialiser le mot de passe oublié"
				>
					{$t('auth.login.forgot_password')}
				</a>
			</div>
			<input
				id="password"
				name="password"
				type="password"
				autocomplete="current-password"
				placeholder={$t('auth.login.password_placeholder')}
				class="input"
				class:border-red-400={passwordError || (form?.field === 'password')}
				disabled={loading}
				data-coco-desc="Champ mot de passe pour se connecter"
				aria-describedby={passwordError ? 'password-error' : undefined}
				aria-invalid={!!passwordError}
			/>
			{#if passwordError}
				<p id="password-error" class="error-msg">{passwordError}</p>
			{:else if form?.field === 'password'}
				<p id="password-error" class="error-msg">{resolveError(form.message)}</p>
			{/if}
		</div>

		<!-- Submit button -->
		<button
			type="submit"
			class="btn-primary w-full"
			disabled={loading}
			data-coco-desc="Bouton pour se connecter à son compte"
		>
			{#if loading}
				<svg
					class="animate-spin w-4 h-4"
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					aria-hidden="true"
				>
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
					<path
						class="opacity-75"
						fill="currentColor"
						d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
					/>
				</svg>
				{$t('auth.login.submitting')}
			{:else}
				{$t('auth.login.submit')}
			{/if}
		</button>
	</form>

	<!-- Register link -->
	<p class="mt-6 text-center text-sm" style="color: var(--color-text-muted)">
		{$t('auth.login.no_account')}
		<a
			href="/register"
			class="font-medium hover:underline ml-1"
			style="color: var(--color-brand-gold)"
			data-coco-desc="Lien pour créer un nouveau compte"
		>
			{$t('auth.login.register_link')}
		</a>
	</p>
</AuthLayout>
