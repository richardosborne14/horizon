#!/usr/bin/env bash
# deploy-demo.sh — Deploy Communauté Coiffure to the DEMO server
#
# Deploys from your LOCAL machine to the Hetzner demo server via SSH.
# Uses three compose files: base + prod overrides + demo-specific overrides.
#
# Usage:
#   ./scripts/deploy-demo.sh
#
# Prerequisites:
#   - Server provisioned:      ./scripts/provision-hetzner.sh
#   - GitHub access set up:    ./scripts/setup-github-deploy-key.sh
#   - Demo env uploaded:       scp .env.demo comcoi@<IP>:/opt/comcoi/.env
#   - HETZNER_SERVER_IP set in .env
#   - ~/.ssh/comcoi_hetzner exists
#   - DNS A record:            comcoi-demo.digitalbricks.io → <server_ip>
#
# What this script does:
#   1. SSHes into the Hetzner demo server
#   2. Pulls latest code from git (via SSH deploy key)
#   3. Builds Docker images (base + prod + demo compose files)
#   4. Runs Alembic migrations
#   5. Restarts services (db, backend, frontend, caddy)
#   6. Health checks
#   7. Seeds demo user (smoketest@comcoi.fr) if not already present

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    export $(grep -E '^HETZNER_(SERVER_IP|SSH_KEY_PATH|SSH_KEY_NAME)=' "${PROJECT_ROOT}/.env" | xargs)
    set +a
fi

: "${HETZNER_SERVER_IP:?ERROR: HETZNER_SERVER_IP not set. Run provision-hetzner.sh first.}"
: "${HETZNER_SSH_KEY_PATH:?ERROR: HETZNER_SSH_KEY_PATH not set.}"

SSH_KEY="${HETZNER_SSH_KEY_PATH/#\~/$HOME}"

if [[ ! -f "$SSH_KEY" ]]; then
    echo "❌ SSH key not found at: $SSH_KEY"
    echo "   Run scripts/provision-hetzner.sh to generate and upload it."
    exit 1
fi

SSH_USER="comcoi"
REMOTE="${SSH_USER}@${HETZNER_SERVER_IP}"
SSH_OPTS="-i ${SSH_KEY} -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"
REMOTE_DIR="/opt/comcoi"
# WHY three compose files:
#   docker-compose.yml         — base service definitions (db, backend, frontend, caddy)
#   docker-compose.prod.yml    — production overrides (no hot-reload, restart:always, etc.)
#   docker-compose.demo.yml    — demo-specific (domain, DB password, staging APP_ENV, Caddy config)
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.demo.yml"
DEMO_URL="https://comcoi-demo.digitalbricks.io"

echo "🚀 Communauté Coiffure — Deploy to DEMO server"
echo "   Server:    ${HETZNER_SERVER_IP}"
echo "   User:      ${SSH_USER}"
echo "   Directory: ${REMOTE_DIR}"
echo "   URL:       ${DEMO_URL}"
echo "   Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ── Test SSH connectivity ──────────────────────────────────────────────────────
echo "🔌 Testing SSH connection..."
# shellcheck disable=SC2086
ssh $SSH_OPTS "$REMOTE" "echo '   ✅ Connected'" || {
    echo "❌ SSH connection failed. Check HETZNER_SERVER_IP and HETZNER_SSH_KEY_PATH."
    exit 1
}
echo ""

# ── Verify .env exists on server ──────────────────────────────────────────────
echo "🔍 Checking .env on server..."
# shellcheck disable=SC2086
ENV_EXISTS=$(ssh $SSH_OPTS "$REMOTE" "test -f ${REMOTE_DIR}/.env && echo 'yes' || echo 'no'")
if [[ "$ENV_EXISTS" == "no" ]]; then
    echo "❌ .env not found at ${REMOTE_DIR}/.env on the server."
    echo ""
    echo "   Generate and upload it first:"
    echo "   ./scripts/generate-demo-env.sh"
    echo "   scp -i ${SSH_KEY} .env.demo ${REMOTE}:${REMOTE_DIR}/.env"
    exit 1
fi

# Check POSTGRES_PASSWORD is set (required by docker-compose.demo.yml)
# shellcheck disable=SC2086
PG_CHECK=$(ssh $SSH_OPTS "$REMOTE" "grep -c 'POSTGRES_PASSWORD=' ${REMOTE_DIR}/.env 2>/dev/null || echo 0")
if [[ "$PG_CHECK" == "0" ]]; then
    echo "❌ POSTGRES_PASSWORD not found in server .env."
    echo "   Re-upload with: scp -i ${SSH_KEY} .env.demo ${REMOTE}:${REMOTE_DIR}/.env"
    exit 1
fi
echo "   ✅ .env OK"
echo ""

# ── Run deployment on the remote server ───────────────────────────────────────
echo "🏗️  Running deployment on server..."
# shellcheck disable=SC2086
ssh $SSH_OPTS "$REMOTE" bash -s << REMOTE_SCRIPT
set -euo pipefail
cd "${REMOTE_DIR}"

echo "  📥 Pulling latest code..."
git pull origin main

echo "  🔨 Building Docker images..."
docker compose ${COMPOSE_FILES} build

echo "  🗄️  Starting database..."
docker compose ${COMPOSE_FILES} up -d db
echo "  ⏳ Waiting for database to be ready..."
timeout 60 bash -c 'until docker compose ${COMPOSE_FILES} exec -T db pg_isready -U comcoi -d comcoi 2>/dev/null; do sleep 2; done'
echo "  ✅ Database ready"

echo "  🗃️  Running migrations..."
# WHY PYTHONPATH=/app: docker compose run starts a fresh container; the /app directory
# must be explicitly in sys.path for alembic/env.py to find the 'app' package.
# WHY heads not head: defensive against accidental multi-branch migrations (e.g. wrong down_revision)
docker compose ${COMPOSE_FILES} run --rm -e PYTHONPATH=/app backend alembic upgrade heads

echo "  🌱 Seeding demo data..."
docker compose ${COMPOSE_FILES} run --rm backend python scripts/seed.py || echo "  ℹ️  Seed already ran or not applicable — continuing"

echo "  ♻️  Starting all services..."
# WHY --force-recreate: without it, docker compose up -d will NOT replace a running
# container when only the image *content* changes (same tag, new digest). This caused
# the stale-image bug where the old frontend container kept serving old code after a
# rebuild. --force-recreate guarantees containers are always replaced with the new image.
docker compose ${COMPOSE_FILES} up -d --no-deps --force-recreate backend frontend caddy

echo "  🩺 Waiting for backend to start (10s)..."
sleep 10

HEALTH=\$(curl -sf http://localhost:8000/api/health 2>/dev/null || echo "FAILED")
if echo "\$HEALTH" | grep -q '"status":"ok"'; then
    echo "  ✅ Backend healthy: \$HEALTH"
else
    echo "  ⚠️  Backend health check failed — logs:"
    docker compose ${COMPOSE_FILES} logs backend --tail=30
fi

echo ""
echo "  📋 Running containers:"
docker compose ${COMPOSE_FILES} ps
REMOTE_SCRIPT

echo ""
echo "✅ Demo deploy complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   App:         ${DEMO_URL}"
echo "   API health:  ${DEMO_URL}/api/health"
echo "   API docs:    ${DEMO_URL}/api/docs  (staging env)"
echo "   Login:       smoketest@comcoi.fr / Password123!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "ℹ️  Note: Caddy provisions a TLS cert on first request."
echo "   If you see a TLS error, wait 30 seconds and refresh."
echo ""
echo "🔍 To check Caddy logs if TLS fails:"
echo "   ssh -i ${SSH_KEY} ${REMOTE} 'docker compose ${COMPOSE_FILES} logs caddy --tail=30'"
