import { sveltekit } from '@sveltejs/kit/vite';
// WHY vitest/config: defineConfig from vitest/config extends vite's version to
// include the `test` property in its TypeScript types. Without this the TS
// compiler complains "Object literal may only specify known properties".
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	// WHY test config here: vitest reads from vite.config.ts by default in a Vite project.
	// 'node' environment is correct for pure logic tests (no DOM required).
	// Include only .test.ts files — excludes Svelte component files from test runs.
	test: {
		environment: 'node',
		include: ['src/**/*.test.ts']
	},
	server: {
		// Allow access from Docker network.
		// Port 47178: chosen to avoid collisions with other dev projects on this machine.
		host: '0.0.0.0',
		port: 47178,
		strictPort: true,
		// WHY env var: Inside Docker the backend is at http://backend:8000 (Docker
		// internal DNS), not localhost. BACKEND_URL is injected via docker-compose.yml
		// so the Vite dev proxy reaches the right host.  Falls back to the
		// host-machine port-mapped address for running outside Docker.
		proxy: {
			'/api': {
				target: process.env.BACKEND_URL || 'http://localhost:47002',
				changeOrigin: true
			}
		}
	}
});
