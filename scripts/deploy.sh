#!/usr/bin/env bash
# deploy.sh — Communauté Coiffure deployment script
#
# Deploys from your LOCAL machine to the Hetzner production server via SSH.
# Requires the server to already be provisioned (run provision-hetzner.sh first).
#
# Usage:
#   ./scripts/deploy.sh
#
# Prerequisites:
#   - Server provisioned: ./scripts/provision-hetzner.sh
#   - HETZNER_SERVER_IP set in .env (or exported in your shell)
#   - HETZNER_SSH_KEY_PATH set in .env (or exported in your shell)
#   - .env file present ON THE SERVER at /opt/comcoi/.env
#
# What this script does:
#   1. SSHes into the Hetzner server
#   2. Pulls latest code from git
#   3. Builds Docker images
#   4. Runs Alembic migrations
#   5. Restarts services (backend, frontend, caddy)
#   6. Health checks

set -euo pipefail

# ── Load .env from project root if present ────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    # Export only the Hetzner vars we need — avoid polluting the environment
    set -a
    # shellcheck disable=SC2046
    export $(grep -E '^HETZNER_(SERVER_IP|SSH_KEY_PATH|SSH_KEY_NAME)=' "${PROJECT_ROOT}/.env" | xargs)
    set +a
fi

# ── Validate required vars ─────────────────────────────────────────────────────
: "${HETZNER_SERVER_IP:?ERROR: HETZNER_SERVER_IP not set. Run provision-hetzner.sh first.}"
: "${HETZNER_SSH_KEY_PATH:?ERROR: HETZNER_SSH_KEY_PATH not set. Check your .env.}"

# Expand ~ in path
SSH_KEY="${HETZNER_SSH_KEY_PATH/#\~/$HOME}"

if [[ ! -f "$SSH_KEY" ]]; then
    echo "❌ SSH key not found at: $SSH_KEY"
    echo "   Run scripts/provision-hetzner.sh to generate and upload it."
    exit 1
fi

SSH_USER="comcoi"
REMOTE="$SSH_USER@$HETZNER_SERVER_IP"
SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"
REMOTE_DIR="/opt/comcoi"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

echo "🚀 Communauté Coiffure — Deploy to Hetzner"
echo "   Server:    $HETZNER_SERVER_IP"
echo "   User:      $SSH_USER"
echo "   Directory: $REMOTE_DIR"
echo "   Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ── Test SSH connectivity ──────────────────────────────────────────────────────
echo "� Testing SSH connection..."
# shellcheck disable=SC2086
ssh $SSH_OPTS "$REMOTE" "echo '   ✅ Connected'" || {
    echo "❌ SSH connection failed. Check HETZNER_SERVER_IP and HETZNER_SSH_KEY_PATH."
    exit 1
}
echo ""

# ── Run deployment on the remote server ───────────────────────────────────────
echo "� Running deployment on server..."
# shellcheck disable=SC2086
ssh $SSH_OPTS "$REMOTE" bash -s << REMOTE_SCRIPT
set -euo pipefail
cd "${REMOTE_DIR}"

echo "  📥 Pulling latest code..."
git pull origin main

echo "  🔨 Building Docker images..."
docker compose ${COMPOSE_FILES} build

echo "  🗄️  Ensuring database is running..."
docker compose ${COMPOSE_FILES} up -d db
timeout 30 bash -c 'until docker compose ${COMPOSE_FILES} exec -T db pg_isready -U comcoi -d comcoi 2>/dev/null; do sleep 2; done'

echo "  🗃️  Running migrations..."
# WHY heads not head: defensive against accidental multi-branch migrations
docker compose ${COMPOSE_FILES} run --rm backend alembic upgrade heads

echo "  ♻️  Restarting services..."
docker compose ${COMPOSE_FILES} up -d --no-deps backend frontend caddy

echo "  🩺 Waiting for backend to start..."
sleep 5
HEALTH=\$(curl -sf http://localhost:8000/api/health 2>/dev/null || echo "FAILED")
if echo "\$HEALTH" | grep -q '"status":"ok"'; then
    echo "  ✅ Backend is healthy"
else
    echo "  ⚠️  Backend health check failed — check logs:"
    echo "     docker compose ${COMPOSE_FILES} logs backend --tail=50"
fi

echo "  📋 Running containers:"
docker compose ${COMPOSE_FILES} ps
REMOTE_SCRIPT

echo ""
echo "✅ Deploy complete!"
echo "   Frontend: https://app.communaute-coiffure.fr"
echo "   API:      https://api.communaute-coiffure.fr/api/health"
echo ""
