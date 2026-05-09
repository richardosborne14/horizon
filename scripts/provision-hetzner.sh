#!/usr/bin/env bash
# provision-hetzner.sh — Communauté Coiffure server provisioning script
#
# One-time script to create the production server on Hetzner Cloud.
# Run this ONCE from your local machine before the first deploy.
#
# What this does:
#   1. Generates an SSH keypair locally (~/.ssh/comcoi_hetzner)
#   2. Uploads the public key to Hetzner via the Cloud API
#   3. Creates a CX22 VPS in Nuremberg (nbg1) running Ubuntu 24.04
#   4. Waits for the server to be ready
#   5. SSHes in and installs Docker + Docker Compose + git
#   6. Creates the deploy user and clones the repo
#   7. Prints the server IP and next steps
#
# Prerequisites:
#   - HETZNER_API_TOKEN in your .env file (Read+Write token)
#   - jq installed locally: brew install jq
#   - curl installed locally (standard on macOS)
#
# Usage:
#   ./scripts/provision-hetzner.sh
#
# After this runs:
#   1. Copy your production .env to the server:
#      scp -i ~/.ssh/comcoi_hetzner .env.prod comcoi@<SERVER_IP>:/opt/comcoi/.env
#   2. Run the first deploy:
#      ./scripts/deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC2046
    export $(grep -E '^HETZNER_API_TOKEN=' "${PROJECT_ROOT}/.env" | xargs)
    set +a
fi

: "${HETZNER_API_TOKEN:?ERROR: HETZNER_API_TOKEN not set in .env. Get one from https://console.hetzner.cloud}"

# ── Configuration ──────────────────────────────────────────────────────────────
HETZNER_API="https://api.hetzner.cloud/v1"
SERVER_NAME="comcoi-prod"
SERVER_TYPE="cx23"          # 2 vCPU, 4 GB RAM, 40 GB SSD — ~€4.35/month (cx22 deprecated Apr 2026)
LOCATION="nbg1"             # Nuremberg, Germany (EU data residency)
IMAGE="ubuntu-24.04"
SSH_KEY_NAME="comcoi-deploy"
SSH_KEY_LOCAL="${HOME}/.ssh/comcoi_hetzner"
SSH_KEY_PUB="${SSH_KEY_LOCAL}.pub"
DEPLOY_USER="comcoi"
REMOTE_DIR="/opt/comcoi"

echo "🏗️  Communauté Coiffure — Hetzner Provisioning"
echo "   Server name: $SERVER_NAME"
echo "   Server type: $SERVER_TYPE (2 vCPU, 4 GB RAM)"
echo "   Location:    $LOCATION (Nuremberg, Germany)"
echo "   Image:       $IMAGE"
echo ""

# ── 1. Generate SSH keypair ───────────────────────────────────────────────────
if [[ -f "$SSH_KEY_LOCAL" ]]; then
    echo "🔑 SSH key already exists at $SSH_KEY_LOCAL — reusing it."
else
    echo "🔑 Generating SSH keypair..."
    ssh-keygen -t ed25519 -f "$SSH_KEY_LOCAL" -C "comcoi-deploy-$(date +%Y%m%d)" -N ""
    chmod 600 "$SSH_KEY_LOCAL"
    echo "   ✅ Key saved to $SSH_KEY_LOCAL"
fi
echo ""

# ── 2. Upload public key to Hetzner ──────────────────────────────────────────
echo "📤 Uploading public key to Hetzner..."
PUBLIC_KEY=$(cat "$SSH_KEY_PUB")

# Check if key already exists
EXISTING_KEY=$(curl -sf \
    -H "Authorization: Bearer $HETZNER_API_TOKEN" \
    "${HETZNER_API}/ssh_keys" | \
    jq -r ".ssh_keys[] | select(.name == \"${SSH_KEY_NAME}\") | .id" 2>/dev/null || echo "")

if [[ -n "$EXISTING_KEY" ]]; then
    echo "   Key '$SSH_KEY_NAME' already exists in Hetzner (id: $EXISTING_KEY) — skipping upload."
    SSH_KEY_ID="$EXISTING_KEY"
else
    UPLOAD_RESPONSE=$(curl -sf \
        -X POST \
        -H "Authorization: Bearer $HETZNER_API_TOKEN" \
        -H "Content-Type: application/json" \
        "${HETZNER_API}/ssh_keys" \
        -d "{\"name\": \"${SSH_KEY_NAME}\", \"public_key\": \"${PUBLIC_KEY}\"}")

    SSH_KEY_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.ssh_key.id')
    echo "   ✅ Key uploaded (id: $SSH_KEY_ID)"
fi
echo ""

# ── 3. Create server ──────────────────────────────────────────────────────────
echo "🖥️  Creating Hetzner server '$SERVER_NAME'..."

# Check if server already exists
EXISTING_SERVER=$(curl -sf \
    -H "Authorization: Bearer $HETZNER_API_TOKEN" \
    "${HETZNER_API}/servers?name=${SERVER_NAME}" | \
    jq -r '.servers[0].id // empty' 2>/dev/null || echo "")

if [[ -n "$EXISTING_SERVER" ]]; then
    echo "   Server '$SERVER_NAME' already exists (id: $EXISTING_SERVER)."
    SERVER_ID="$EXISTING_SERVER"
    SERVER_IP=$(curl -sf \
        -H "Authorization: Bearer $HETZNER_API_TOKEN" \
        "${HETZNER_API}/servers/${SERVER_ID}" | \
        jq -r '.server.public_net.ipv4.ip')
else
    # Cloud-init: run initial setup automatically on first boot
    CLOUD_INIT=$(cat << 'CLOUDINIT'
#cloud-config
package_update: true
package_upgrade: true
packages:
  - curl
  - git
  - ca-certificates
  - gnupg
  - ufw

runcmd:
  # Install Docker
  - curl -fsSL https://get.docker.com | sh
  - systemctl enable docker
  - systemctl start docker

  # Create deploy user
  - useradd -m -s /bin/bash comcoi
  - usermod -aG docker comcoi
  - mkdir -p /home/comcoi/.ssh
  - cp /root/.ssh/authorized_keys /home/comcoi/.ssh/
  - chown -R comcoi:comcoi /home/comcoi/.ssh
  - chmod 700 /home/comcoi/.ssh
  - chmod 600 /home/comcoi/.ssh/authorized_keys

  # Set up deployment directory
  - mkdir -p /opt/comcoi
  - chown comcoi:comcoi /opt/comcoi

  # Configure UFW firewall
  - ufw default deny incoming
  - ufw default allow outgoing
  - ufw allow ssh
  - ufw allow http
  - ufw allow https
  - ufw --force enable

  # Create backups directory
  - mkdir -p /opt/comcoi/backups
  - chown comcoi:comcoi /opt/comcoi/backups
CLOUDINIT
)

    CREATE_RESPONSE=$(curl -sf \
        -X POST \
        -H "Authorization: Bearer $HETZNER_API_TOKEN" \
        -H "Content-Type: application/json" \
        "${HETZNER_API}/servers" \
        -d "{
            \"name\": \"${SERVER_NAME}\",
            \"server_type\": \"${SERVER_TYPE}\",
            \"location\": \"${LOCATION}\",
            \"image\": \"${IMAGE}\",
            \"ssh_keys\": [${SSH_KEY_ID}],
            \"user_data\": $(echo "$CLOUD_INIT" | jq -Rs '.'),
            \"labels\": {\"project\": \"comcoi\", \"env\": \"production\"}
        }")

    SERVER_ID=$(echo "$CREATE_RESPONSE" | jq -r '.server.id')
    SERVER_IP=$(echo "$CREATE_RESPONSE" | jq -r '.server.public_net.ipv4.ip')
    echo "   ✅ Server created (id: $SERVER_ID)"
fi

echo "   IP: $SERVER_IP"
echo ""

# ── 4. Wait for server to be running ─────────────────────────────────────────
echo "⏳ Waiting for server to be ready (this takes ~2 minutes)..."
MAX_WAIT=180
WAITED=0
while true; do
    STATUS=$(curl -sf \
        -H "Authorization: Bearer $HETZNER_API_TOKEN" \
        "${HETZNER_API}/servers/${SERVER_ID}" | \
        jq -r '.server.status')

    if [[ "$STATUS" == "running" ]]; then
        echo "   ✅ Server is running!"
        break
    fi

    if [[ $WAITED -ge $MAX_WAIT ]]; then
        echo "   ❌ Timed out waiting for server. Check Hetzner console."
        exit 1
    fi

    echo "   Status: $STATUS — waiting..."
    sleep 10
    WAITED=$((WAITED + 10))
done
echo ""

# ── 5. Wait for SSH to be ready ───────────────────────────────────────────────
echo "🔌 Waiting for SSH to be available..."
SSH_OPTS="-i $SSH_KEY_LOCAL -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes"
MAX_SSH=120
WAITED_SSH=0
while true; do
    # shellcheck disable=SC2086
    if ssh $SSH_OPTS "root@$SERVER_IP" "echo ok" &>/dev/null; then
        echo "   ✅ SSH is ready!"
        break
    fi

    if [[ $WAITED_SSH -ge $MAX_SSH ]]; then
        echo "   ⚠️  SSH not ready after ${MAX_SSH}s — cloud-init may still be running."
        echo "   Try manually: ssh -i $SSH_KEY_LOCAL root@$SERVER_IP"
        break
    fi

    echo "   Waiting for SSH... (${WAITED_SSH}s)"
    sleep 10
    WAITED_SSH=$((WAITED_SSH + 10))
done
echo ""

# ── 6. Ensure /opt/comcoi directory is ready on the server ───────────────────
# WHY: The repo is private — we can't clone with HTTPS without credentials.
# Clone is deferred to scripts/setup-github-deploy-key.sh which sets up
# an SSH deploy key and clones via SSH. Here we just ensure the directory exists.
echo "📦 Preparing deployment directory on server..."
# shellcheck disable=SC2086
ssh $SSH_OPTS "comcoi@$SERVER_IP" bash -s << REMOTE_SETUP || ssh $SSH_OPTS "root@$SERVER_IP" bash -s << ROOT_SETUP
    mkdir -p ${REMOTE_DIR}
    echo "   ✅ Directory ready: ${REMOTE_DIR}"
REMOTE_SETUP
    mkdir -p ${REMOTE_DIR}
    chown -R comcoi:comcoi ${REMOTE_DIR}
    echo "   ✅ Directory ready: ${REMOTE_DIR} (as root)"
ROOT_SETUP

echo ""

# ── 7. Save IP to .env ────────────────────────────────────────────────────────
echo "💾 Saving server IP to .env..."
if grep -q "^HETZNER_SERVER_IP=" "${PROJECT_ROOT}/.env"; then
    sed -i.bak "s|^HETZNER_SERVER_IP=.*|HETZNER_SERVER_IP=${SERVER_IP}|" "${PROJECT_ROOT}/.env"
else
    echo "HETZNER_SERVER_IP=${SERVER_IP}" >> "${PROJECT_ROOT}/.env"
fi
echo "   ✅ HETZNER_SERVER_IP=${SERVER_IP} saved to .env"
echo ""

# ── Done! Print next steps ────────────────────────────────────────────────────
echo "✅ Server provisioned successfully!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔑 SSH access:"
echo "   ssh -i $SSH_KEY_LOCAL comcoi@$SERVER_IP"
echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1. Create your production .env file with real secrets:"
echo "   cp .env.example .env.production"
echo "   # Fill in all values in .env.production"
echo ""
echo "2. Upload the production .env to the server:"
echo "   scp -i $SSH_KEY_LOCAL .env.production comcoi@$SERVER_IP:${REMOTE_DIR}/.env"
echo ""
echo "3. Set up GitHub deploy key and clone the repo:"
echo "   ./scripts/setup-github-deploy-key.sh"
echo ""
echo "4. Point DNS A records to: $SERVER_IP"
echo "   For demo:       comcoi-demo.digitalbricks.io → $SERVER_IP"
echo "   For production: app.communaute-coiffure.fr   → $SERVER_IP"
echo "                   api.communaute-coiffure.fr   → $SERVER_IP"
echo ""
echo "5. Run the deploy:"
echo "   Demo:       ./scripts/deploy-demo.sh"
echo "   Production: ./scripts/deploy.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
