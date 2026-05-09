#!/usr/bin/env bash
# backup-db.sh — PostgreSQL database backup script
#
# Creates a timestamped pg_dump of the comcoi database and compresses it.
# Intended to be run manually or via cron on the production server.
#
# Usage:
#   ./scripts/backup-db.sh
#
# Cron example (daily at 3am):
#   0 3 * * * /path/to/comcoi-v2/scripts/backup-db.sh >> /var/log/comcoi-backup.log 2>&1
#
# Backup location: ./backups/ (relative to project root)
# Format: comcoi_YYYYMMDD_HHMMSS.sql.gz
# Retention: keeps last 30 backups (older ones deleted automatically)

set -euo pipefail

TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${PROJECT_ROOT}/backups"
BACKUP_FILE="${BACKUP_DIR}/comcoi_${TIMESTAMP}.sql"
RETAIN_COUNT=30

echo "📦 Database backup starting..."
echo "   Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Run pg_dump via the running db container
# WHY: Uses Docker exec to avoid needing psql installed on the host
echo "   Dumping database..."
docker compose -f "${PROJECT_ROOT}/docker-compose.yml" \
    exec -T db \
    pg_dump -U comcoi --no-password comcoi \
    > "${BACKUP_FILE}"

# Compress the dump
echo "   Compressing..."
gzip "${BACKUP_FILE}"

FINAL_FILE="${BACKUP_FILE}.gz"
FILE_SIZE=$(du -sh "${FINAL_FILE}" | cut -f1)

echo "   ✅ Backup saved: ${FINAL_FILE} (${FILE_SIZE})"

# ── Retention: keep only the last N backups ────────────────────────────────────
echo "   Cleaning old backups (keeping last ${RETAIN_COUNT})..."
ls -t "${BACKUP_DIR}"/comcoi_*.sql.gz 2>/dev/null | \
    tail -n "+$((RETAIN_COUNT + 1))" | \
    xargs -r rm --
REMAINING=$(ls "${BACKUP_DIR}"/comcoi_*.sql.gz 2>/dev/null | wc -l)
echo "   ${REMAINING} backup(s) retained in ${BACKUP_DIR}"

echo ""
echo "✅ Backup complete!"
