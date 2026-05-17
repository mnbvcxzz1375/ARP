#!/usr/bin/env bash
set -euo pipefail

DATABASE_URL_VALUE="${DATABASE_URL:-}"
BACKUP_DIR_VALUE="${BACKUP_DIR:-backups/postgres}"
RETENTION_DAYS_VALUE="${RETENTION_DAYS:-14}"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: ./scripts/backup/postgres_backup.sh [--dry-run] [--database-url <url>] [--backup-dir <dir>] [--retention-days <days>]

Creates a PostgreSQL custom-format backup and SHA-256 checksum.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --database-url) DATABASE_URL_VALUE="$2"; shift 2 ;;
    --backup-dir) BACKUP_DIR_VALUE="$2"; shift 2 ;;
    --retention-days) RETENTION_DAYS_VALUE="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

timestamp="$(date -u +%Y%m%d_%H%M%S)"
backup_path="${BACKUP_DIR_VALUE}/agentnet_${timestamp}.dump"
checksum_path="${backup_path}.sha256"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY RUN: would create backup directory: ${BACKUP_DIR_VALUE}"
  echo "DRY RUN: would run pg_dump --format=custom --file ${backup_path} <DATABASE_URL>"
  echo "DRY RUN: would write checksum: ${checksum_path}"
  echo "DRY RUN: would prune backups older than ${RETENTION_DAYS_VALUE} days"
  exit 0
fi

if [[ -z "$DATABASE_URL_VALUE" ]]; then
  echo "DATABASE_URL is required. Set DATABASE_URL or pass --database-url." >&2
  exit 1
fi
command -v pg_dump >/dev/null 2>&1 || { echo "pg_dump was not found on PATH." >&2; exit 1; }

mkdir -p "$BACKUP_DIR_VALUE"
pg_dump --format=custom --file "$backup_path" "$DATABASE_URL_VALUE"
sha256sum "$backup_path" > "$checksum_path"

if [[ "$RETENTION_DAYS_VALUE" -gt 0 ]]; then
  find "$BACKUP_DIR_VALUE" -type f \( -name 'agentnet_*.dump' -o -name 'agentnet_*.dump.sha256' \) -mtime "+${RETENTION_DAYS_VALUE}" -delete
fi

echo "Backup created: ${backup_path}"
echo "Checksum created: ${checksum_path}"
