#!/usr/bin/env bash
# setup-github-deploy-key.sh — Configure GitHub access on the demo server
#
# The GitHub repo is private. This script:
#   1. Generates an ed25519 deploy key on the remote server
#   2. Prints the public key for you to add to GitHub
#   3. Waits for your confirmation
#   4. Configures SSH on the server to use this key for github.com
#   5. Tests the connection and clones / updates the repo
#
# Run this AFTER provision-hetzner.sh, BEFORE deploy-demo.sh:
#   ./scripts/setup-github-deploy-key.sh
#
# Prerequisites:
#   - HETZNER_SERVER_IP set in .env (done by provision-hetzner.sh)
#   - ~/.ssh/comcoi_hetzner exists (done by provision-hetzner.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── Load .env ──────────────────────────────────────────────────────────────────
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    export $(grep -E '^HETZNER_(SERVER_IP|SSH_KEY_PATH)=' "${PROJECT_ROOT}/.env" | xargs)
    set +a
fi

: "${HETZNER_SERVER_IP:?ERROR: HETZNER_SERVER_IP not set. Run provision-hetzner.sh first.}"
: "${HETZNER_SSH_KEY_PATH:?ERROR: HETZNER_SSH_KEY_PATH not set.}"

SSH_KEY="${HETZNER_SSH_KEY_PATH/#\~/$HOME}"
SSH_USER="comcoi"
REMOTE="${SSH_USER}@${HETZNER_SERVER_IP}"
SSH_OPTS="-i ${SSH_KEY} -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"
REMOTE_DIR="/opt/comcoi"
GITHUB_REPO="git@github.com:richardosborne14/comcoi-v2.git"

echo "🔑 Setting up GitHub deploy key on demo server"
echo "   Server: ${HETZNER_SERVER_IP}"
echo ""

# ── Step 1: Generate deploy key on the server ─────────────────────────────────
echo "📋 Generating deploy key on server..."
# shellcheck disable=SC2086
DEPLOY_PUB_KEY=$(ssh $SSH_OPTS "$REMOTE" bash -s << 'REMOTE_KEYGEN'
set -euo pipefail
KEYFILE="${HOME}/.ssh/github_deploy"

if [[ ! -f "$KEYFILE" ]]; then
    ssh-keygen -t ed25519 -f "$KEYFILE" -C "comcoi-demo-deploy" -N ""
    chmod 600 "$KEYFILE"
    echo "KEY_GENERATED" >&2
else
    echo "KEY_EXISTS" >&2
fi

cat "${KEYFILE}.pub"
REMOTE_KEYGEN
)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚨 ACTION REQUIRED — Add this deploy key to GitHub:"
echo ""
echo "   Repository: https://github.com/richardosborne14/comcoi-v2/settings/keys"
echo ""
echo "   Title:     comcoi-demo-deploy"
echo "   Key:       (copy the line below)"
echo ""
echo "${DEPLOY_PUB_KEY}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Steps:"
echo "  1. Open the URL above in your browser"
echo "  2. Click 'Add deploy key'"
echo "  3. Paste the key above, tick 'Allow write access' is NOT needed"
echo "  4. Click 'Add key'"
echo ""
read -r -p "Press ENTER when you've added the key to GitHub... "
echo ""

# ── Step 2: Configure SSH on the server to use the deploy key ─────────────────
echo "🔧 Configuring SSH on server for GitHub..."
# shellcheck disable=SC2086
ssh $SSH_OPTS "$REMOTE" bash -s << 'REMOTE_CONFIG'
set -euo pipefail
KEYFILE="${HOME}/.ssh/github_deploy"
SSH_CONFIG="${HOME}/.ssh/config"

# Add/update SSH config entry for github.com
if grep -q "Host github.com" "$SSH_CONFIG" 2>/dev/null; then
    echo "   SSH config already has github.com entry — skipping"
else
    cat >> "$SSH_CONFIG" << 'SSHCONFIG'

Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
SSHCONFIG
    chmod 600 "$SSH_CONFIG"
    echo "   ✅ SSH config updated"
fi
REMOTE_CONFIG

# ── Step 3: Test GitHub SSH connection ────────────────────────────────────────
echo "🧪 Testing GitHub SSH connection..."
# shellcheck disable=SC2086
ssh $SSH_OPTS "$REMOTE" "ssh -T git@github.com 2>&1 || true" | grep -i "successfully authenticated" && echo "   ✅ GitHub SSH auth works!" || {
    echo "   ⚠️  GitHub connection test returned unexpected output — checking manually..."
    # shellcheck disable=SC2086
    ssh $SSH_OPTS "$REMOTE" "ssh -T git@github.com 2>&1 || true"
}

# ── Step 4: Clone or update the repo ──────────────────────────────────────────
echo ""
echo "📦 Cloning / updating repo on server..."
# shellcheck disable=SC2086
ssh $SSH_OPTS "$REMOTE" bash << REMOTE_CLONE
set -euo pipefail

if [[ -d "${REMOTE_DIR}/.git" ]]; then
    echo "   Repo already cloned — pulling latest..."
    cd "${REMOTE_DIR}"
    # Update remote to SSH URL in case it was cloned with HTTPS
    git remote set-url origin ${GITHUB_REPO}
    git pull origin main
    echo "   ✅ Repo updated"
else
    echo "   Cloning repo..."
    git clone ${GITHUB_REPO} ${REMOTE_DIR}
    echo "   ✅ Repo cloned"
fi
REMOTE_CLONE

echo ""
echo "✅ GitHub deploy key configured and repo is ready!"
echo ""
echo "📋 Next step: upload your .env.demo and run the first deploy:"
echo ""
echo "   # Update the server IP in .env.demo first:"
echo "   # (provision-hetzner.sh should have already updated .env)"
echo "   # Generate .env.demo if you haven't already:"
echo "   ./scripts/generate-demo-env.sh"
echo ""
echo "   # Upload env to server:"
echo "   scp -i ~/.ssh/comcoi_hetzner .env.demo comcoi@${HETZNER_SERVER_IP}:${REMOTE_DIR}/.env"
echo ""
echo "   # Run first deploy:"
echo "   ./scripts/deploy-demo.sh"
