<!--
  Register page — /register

  Name, email, password, confirm password form.
  On success, server action redirects to /onboarding.
  All text via i18n keys (auth.register.*).
-->
<script lang="ts">
	import { t } from 'svelte-i18n';
	import { enhance } from '$app/forms';
	import AuthLayout from '$lib/components/AuthLayout.svelte';
	import type { ActionData } from './$types';

	export let form: ActionData;

	let loading = false;

	let nameError = '';
	let emailError = '';
	let passwordError = '';
	let confirmError = '';

	/**
	 * Client-side validation before submitting to the server.
	 * Returns false to cancel submission if validation fails.
	 */
	function validate(formData: FormData): boolean {
		nameError = '';
		emailError = '';
		passwordError = '';
		confirmError = '';

		const name = (formData.get('name') as string).trim();
		const email = (formData.get('email') as string).trim();
		const password = formData.get('password') as string;
		const confirmPassword = formData.get('confirm_password') as string;

		if (!name) {
			nameError = $t('errors.required');
			return false;
		}
		if (!email) {
			emailError = $t('errors.required');
			return false;
		}
		if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
			emailError = $t('errors.email_invalid');
			return false;
		}
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

	/**
	 * Map an error code or raw backend message to a displayed string.
	 */
	function resolveError(message: string): string {
		const knownCodes: Record<string, string> = {
			required: $t('errors.required'),
			email_invalid: $t('errors.email_invalid'),
			password_too_short: $t('errors.password_too_short'),
			passwords_no_match: $t('errors.passwords_no_match'),
			email_taken: $t('errors.email_taken'),
			network: $t('errors.network'),
			generic: $t('errors.generic')
		};
		return knownCodes[message] ?? message;
	}
</script>

<svelte:head>
	<title>Créer un compte — Communauté Coiffure</title>
</svelte:head>

<AuthLayout title={$t('auth.register.title')} subtitle={$t('auth.register.subtitle')}>
	<!-- Global API error banner -->
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
		aria-label={$t('auth.register.title')}
	>
		<!-- Full name field -->
		<div class="mb-4">
			<label for="name" class="label" data-coco-desc="Champ pour saisir votre nom complet">
				{$t('auth.register.full_name_label')}
			</label>
			<input
				id="name"
				name="name"
				type="text"
				autocomplete="name"
				placeholder={$t('auth.register.full_name_placeholder')}
				value={form?.name ?? ''}
				class="input"
				class:border-red-400={nameError || form?.field === 'name'}
				disabled={loading}
				data-coco-desc="Champ nom complet pour créer un compte"
				aria-describedby={nameError ? 'name-error' : undefined}
				aria-invalid={!!nameError}
			/>
			{#if nameError}
				<p id="name-error" class="error-msg">{nameError}</p>
			{:else if form?.field === 'name'}
				<p id="name-error" class="error-msg">{resolveError(form.message)}</p>
			{/if}
		</div>

		<!-- Email field -->
		<div class="mb-4">
			<label for="email" class="label" data-coco-desc="Champ pour saisir votre adresse e-mail">
				{$t('auth.register.email_label')}
			</label>
			<input
				id="email"
				name="email"
				type="email"
				autocomplete="email"
				placeholder={$t('auth.register.email_placeholder')}
				value={form?.email ?? ''}
				class="input"
				class:border-red-400={emailError || form?.field === 'email'}
				disabled={loading}
				data-coco-desc="Champ e-mail pour créer un compte"
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
		<div class="mb-4">
			<label for="password" class="label" data-coco-desc="Champ pour choisir votre mot de passe">
				{$t('auth.register.password_label')}
			</label>
			<input
				id="password"
				name="password"
				type="password"
				autocomplete="new-password"
				placeholder={$t('auth.register.password_placeholder')}
				class="input"
				class:border-red-400={passwordError || form?.field === 'password'}
				disabled={loading}
				data-coco-desc="Champ mot de passe pour créer un compte - 8 caractères minimum"
				aria-describedby={passwordError ? 'password-error' : undefined}
				aria-invalid={!!passwordError}
			/>
			{#if passwordError}
				<p id="password-error" class="error-msg">{passwordError}</p>
			{:else if form?.field === 'password'}
				<p id="password-error" class="error-msg">{resolveError(form.message)}</p>
			{/if}
		</div>

		<!-- Confirm password field -->
		<div class="mb-6">
			<label
				for="confirm_password"
				class="label"
				data-coco-desc="Champ pour confirmer votre mot de passe"
			>
				{$t('auth.register.confirm_password_label')}
			</label>
			<input
				id="confirm_password"
				name="confirm_password"
				type="password"
				autocomplete="new-password"
				placeholder={$t('auth.register.confirm_password_placeholder')}
				class="input"
				class:border-red-400={confirmError || form?.field === 'confirm_password'}
				disabled={loading}
				data-coco-desc="Champ confirmation du mot de passe"
				aria-describedby={confirmError ? 'confirm-error' : undefined}
				aria-invalid={!!confirmError}
			/>
			{#if confirmError}
				<p id="confirm-error" class="error-msg">{confirmError}</p>
			{:else if form?.field === 'confirm_password'}
				<p id="confirm-error" class="error-msg">{resolveError(form.message)}</p>
			{/if}
		</div>

		<!-- Submit button -->
		<button
			type="submit"
			class="btn-primary w-full"
			disabled={loading}
			data-coco-desc="Bouton pour créer un compte Communauté Coiffure"
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
				{$t('auth.register.submitting')}
			{:else}
				{$t('auth.register.submit')}
			{/if}
		</button>
	</form>

	<!-- Terms note -->
	<p class="mt-4 text-xs text-center" style="color: var(--color-text-muted)">
		{$t('auth.register.terms_text')}
		<a
			href="/legal/conditions-utilisation"
			class="hover:underline"
			style="color: var(--color-brand-gold)"
			data-coco-desc="Lien vers les conditions d'utilisation"
		>
			{$t('auth.register.terms_link')}
		</a>.
	</p>

	<!-- Login link -->
	<p class="mt-4 text-center text-sm" style="color: var(--color-text-muted)">
		{$t('auth.register.already_account')}
		<a
			href="/login"
			class="font-medium hover:underline ml-1"
			style="color: var(--color-brand-gold)"
			data-coco-desc="Lien vers la page de connexion"
		>
			{$t('auth.register.login_link')}
		</a>
	</p>
</AuthLayout>
