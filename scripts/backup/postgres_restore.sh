#!/usr/bin/env bash
set -euo pipefail

DATABASE_URL_VALUE="${DATABASE_URL:-}"
SNAPSHOT_DIR_VALUE="${BACKUP_DIR:-backups/postgres}"
BACKUP_FILE=""
DRY_RUN=0
YES=0

usage() {
  cat <<'EOF'
Usage: ./scripts/backup/postgres_restore.sh --file <backup.dump> --yes [--database-url <url>]

Restores a PostgreSQL custom-format backup with checksum verification.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes) YES=1; shift ;;
    --file) BACKUP_FILE="$2"; shift 2 ;;
    --database-url) DATABASE_URL_VALUE="$2"; shift 2 ;;
    --snapshot-dir) SNAPSHOT_DIR_VALUE="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY RUN: would require backup file: ${BACKUP_FILE}"
  echo "DRY RUN: would verify <backup>.sha256 checksum when --file is provided"
  echo "DRY RUN: would create pre-restore snapshot in: ${SNAPSHOT_DIR_VALUE}"
  echo "DRY RUN: would run pg_restore --clean --if-exists --dbname <DATABASE_URL> <backup>"
  echo "DRY RUN: would run alembic current and /healthz verification after service restart"
  exit 0
fi

if [[ "$YES" != "1" ]]; then
  echo "Refusing to restore without --yes." >&2
  exit 1
fi
if [[ -z "$BACKUP_FILE" ]]; then
  echo "--file is required for restore." >&2
  exit 1
fi
if [[ -z "$DATABASE_URL_VALUE" ]]; then
  echo "DATABASE_URL is required. Set DATABASE_URL or pass --database-url." >&2
  exit 1
fi
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi
if [[ ! -f "${BACKUP_FILE}.sha256" ]]; then
  echo "Checksum file not found: ${BACKUP_FILE}.sha256" >&2
  exit 1
fi

sha256sum --check "${BACKUP_FILE}.sha256"
command -v pg_dump >/dev/null 2>&1 || { echo "pg_dump was not found on PATH." >&2; exit 1; }
command -v pg_restore >/dev/null 2>&1 || { echo "pg_restore was not found on PATH." >&2; exit 1; }

mkdir -p "$SNAPSHOT_DIR_VALUE"
timestamp="$(date -u +%Y%m%d_%H%M%S)"
snapshot="${SNAPSHOT_DIR_VALUE}/agentnet_pre_restore_${timestamp}.dump"
pg_dump --format=custom --file "$snapshot" "$DATABASE_URL_VALUE"
pg_restore --clean --if-exists --dbname "$DATABASE_URL_VALUE" "$BACKUP_FILE"

echo "Restore completed from: ${BACKUP_FILE}"
echo "Pre-restore snapshot created: ${snapshot}"
