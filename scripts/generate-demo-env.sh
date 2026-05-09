#!/usr/bin/env bash
# generate-demo-env.sh — Generate .env.demo for the demo server
#
# Reads your local .env (which has dev API keys) and produces .env.demo
# with demo-specific overrides: new SECRET_KEY, strong DB password,
# correct domain, staging APP_ENV, and all your existing API keys.
#
# Run this ONCE from your local machine before provisioning:
#   ./scripts/generate-demo-env.sh
#
# Output: .env.demo in the project root
# .env.demo is gitignored — never commit it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_ROOT}/.env"
DEMO_ENV="${PROJECT_ROOT}/.env.demo"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ .env file not found at $ENV_FILE"
    echo "   Copy .env.example to .env and fill in your values first."
    exit 1
fi

# ── Extract values from existing .env (using grep, not source — safer with special chars) ──
# WHY grep not source: SMTP_FROM has <> characters which break bash source parsing
get_env() {
    # Extracts the value of a key from .env, stripping surrounding quotes.
    # Returns empty string (not error) if key is absent — WHY: grep exits 1 on no match
    # and set -euo pipefail would abort the script. The || echo "" prevents that.
    grep -E "^${1}=" "$ENV_FILE" | head -1 | cut -d'=' -f2- | sed "s/^['\"]//;s/['\"]$//" || echo ""
}

ANTHROPIC_API_KEY=$(get_env "ANTHROPIC_API_KEY")
DEEPINFRA_API_KEY=$(get_env "DEEPINFRA_API_KEY")
PERPLEXITY_API_KEY=$(get_env "PERPLEXITY_API_KEY")
STRIPE_SECRET_KEY=$(get_env "STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET=$(get_env "STRIPE_WEBHOOK_SECRET")
STRIPE_PUBLISHABLE_KEY=$(get_env "STRIPE_PUBLISHABLE_KEY")
NOLY_SSO_URL=$(get_env "NOLY_SSO_URL")
SMTP_HOST=$(get_env "SMTP_HOST")
SMTP_PORT=$(get_env "SMTP_PORT")
SMTP_USER=$(get_env "SMTP_USER")
SMTP_PASSWORD=$(get_env "SMTP_PASSWORD")
SMTP_FROM=$(get_env "SMTP_FROM")
PAYSLIP_NOTIFICATION_EMAIL=$(get_env "PAYSLIP_NOTIFICATION_EMAIL")
PAYSLIP_UNIT_PRICE_CENTS=$(get_env "PAYSLIP_UNIT_PRICE_CENTS")
HETZNER_SERVER_IP=$(get_env "HETZNER_SERVER_IP")

# ── Generate fresh secrets for the demo server ───────────────────────────────
echo "🔑 Generating demo secrets..."
DEMO_SECRET_KEY=$(openssl rand -hex 32)
DEMO_POSTGRES_PASSWORD=$(openssl rand -hex 16)

# ── Write .env.demo ────────────────────────────────────────────────────────────
cat > "$DEMO_ENV" << EOF
# ============================================================
# Communauté Coiffure — DEMO environment
# Generated: $(date '+%Y-%m-%d %H:%M:%S')
# Target:    https://comcoi-demo.digitalbricks.io
#
# This file is uploaded to the demo server at /opt/comcoi/.env
# NEVER commit this file to git.
# ============================================================

# --- Database ---
# Uses the POSTGRES_PASSWORD below (matched to docker-compose.demo.yml)
DATABASE_URL=postgresql+asyncpg://comcoi:${DEMO_POSTGRES_PASSWORD}@db:5432/comcoi

# DB container password (used by docker-compose.demo.yml via \${POSTGRES_PASSWORD})
POSTGRES_PASSWORD=${DEMO_POSTGRES_PASSWORD}

# --- Security ---
SECRET_KEY=${DEMO_SECRET_KEY}

# --- AI: Anthropic ---
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY

# --- AI: DeepInfra ---
DEEPINFRA_API_KEY=$DEEPINFRA_API_KEY

# --- AI: Perplexity ---
PERPLEXITY_API_KEY=$PERPLEXITY_API_KEY

# --- Payments: Stripe ---
STRIPE_SECRET_KEY=$STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET=$STRIPE_WEBHOOK_SECRET
STRIPE_PUBLISHABLE_KEY=$STRIPE_PUBLISHABLE_KEY

# --- Noly Compta ---
NOLY_SSO_URL=${NOLY_SSO_URL:-https://app.noly-compta.fr/sso}

# --- Email ---
SMTP_HOST=${SMTP_HOST:-localhost}
SMTP_PORT=${SMTP_PORT:-587}
SMTP_USER=$SMTP_USER
SMTP_PASSWORD=$SMTP_PASSWORD
SMTP_FROM=$SMTP_FROM

# --- Payslip ---
PAYSLIP_NOTIFICATION_EMAIL=${PAYSLIP_NOTIFICATION_EMAIL:-admin@communaute-coiffure.fr}
PAYSLIP_UNIT_PRICE_CENTS=${PAYSLIP_UNIT_PRICE_CENTS:-2880}

# --- App settings ---
# staging: keeps API docs enabled at /api/docs (useful for demo testing)
APP_ENV=staging

# CORS: allow requests from the demo domain
FRONTEND_URL=https://comcoi-demo.digitalbricks.io

# --- Hetzner (used by deploy-demo.sh) ---
HETZNER_SERVER_IP=$HETZNER_SERVER_IP
HETZNER_SSH_KEY_PATH=~/.ssh/comcoi_hetzner
HETZNER_SSH_KEY_NAME=comcoi-deploy

# --- Frontend (SvelteKit runtime, set in docker-compose.demo.yml) ---
# Note: these are overridden by docker-compose.demo.yml environment section.
# They're included here as documentation of what the frontend expects.
# PUBLIC_API_URL=https://comcoi-demo.digitalbricks.io/api
# BACKEND_URL=http://backend:8000
EOF

echo "✅ .env.demo generated at: $DEMO_ENV"
echo ""
echo "   POSTGRES_PASSWORD: ${DEMO_POSTGRES_PASSWORD}"
echo "   SECRET_KEY:        ${DEMO_SECRET_KEY:0:12}... (truncated)"
echo ""
echo "📋 Next step: provision the server, then upload .env.demo:"
echo "   ./scripts/provision-hetzner.sh"
echo "   scp -i ~/.ssh/comcoi_hetzner .env.demo comcoi@<SERVER_IP>:/opt/comcoi/.env"
