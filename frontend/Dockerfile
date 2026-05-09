# ── Build stage ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (layer cache: only re-runs if package files change)
COPY package*.json ./
RUN npm ci

# Build-time env vars required by $env/static/public
# WHY ARG + ENV: Docker ARG is only available during build; setting it as ENV
# makes it visible to child RUN commands (npm run build / vite build).
# The placeholder is safe — it is NOT a secret (publishable key is browser-visible anyway).
# The real key is injected via `build: args:` in docker-compose.override.yml for dev
# and via CI/CD build args in production.
ARG PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_PLACEHOLDER_replace_with_real_key
ENV PUBLIC_STRIPE_PUBLISHABLE_KEY=$PUBLIC_STRIPE_PUBLISHABLE_KEY

ARG PUBLIC_API_URL=/api
ENV PUBLIC_API_URL=$PUBLIC_API_URL

# Copy source and build
COPY . .
RUN npm run build

# ── Production stage ──────────────────────────────────────────────────────────
FROM node:20-alpine AS production

WORKDIR /app

# Only copy the built output and production deps
COPY --from=builder /app/build ./build
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

ENV NODE_ENV=production

# SvelteKit adapter-node outputs to build/index.js
CMD ["node", "build/index.js"]
