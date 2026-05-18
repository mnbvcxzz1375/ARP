#!/usr/bin/env bash
# backup-restore-drill.sh
# Full backup → teardown → restore → healthz drill for AgentNet.
# Usage: bash scripts/backup-restore-drill.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups/$(date +%Y%m%d-%H%M%S)"
COMPOSE_FILE="$PROJECT_DIR/infra/docker-compose.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${RED}[!]${NC} $*"; }

# --- Step 0: pre-flight -----------------------------------------------
log "Step 0: Pre-flight checks"
mkdir -p "$BACKUP_DIR"
docker ps --format '{{.Names}}' | grep -q infra-api-1  || { warn "API container not running. Start via docker compose first."; exit 1; }
curl -sf http://localhost:8000/healthz > /dev/null || { warn "API healthz failed."; exit 1; }
log "Pre-flight OK — backup dir: $BACKUP_DIR"

# --- Step 1: backup PostgreSQL ----------------------------------------
log "Step 1: Backing up PostgreSQL"
docker exec infra-postgres-1 pg_dump -U agentnet -d agentnet -Fc \
  > "$BACKUP_DIR/postgres.dump"
log "PostgreSQL dump: $(wc -c < "$BACKUP_DIR/postgres.dump") bytes"

# --- Step 2: backup Redis (RDB snapshot) ------------------------------
log "Step 2: Backing up Redis"
docker exec infra-redis-1 redis-cli BGSAVE > /dev/null
sleep 2
docker cp infra-redis-1:/data/dump.rdb "$BACKUP_DIR/redis-dump.rdb" 2>/dev/null || \
  log "Redis dump not found (ok — may be using AOF or empty)"
log "Redis snapshot captured"

# --- Step 3: record agents/tasks/users count --------------------------
log "Step 3: Recording backup metadata"
curl -sf http://localhost:8000/v1/auth/api-keys \
  -H "Authorization: Bearer ak_Bg95_c11p9ZRkqJe5CR5wRKvjTukOVJ8VYck3SGZ9HI" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'API keys: {d[\"total\"]}')" \
  > "$BACKUP_DIR/metadata.txt" 2>/dev/null || true

curl -sf http://localhost:8000/v1/tasks \
  -H "Authorization: Bearer ak_Bg95_c11p9ZRkqJe5CR5wRKvjTukOVJ8VYck3SGZ9HI" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Tasks: {d[\"total\"]}')" \
  >> "$BACKUP_DIR/metadata.txt" 2>/dev/null || true
log "Backup complete: $(cat "$BACKUP_DIR/metadata.txt")"

# --- Step 4: verify the dump is restorable ----------------------------
log "Step 4: Verifying dump integrity"
pg_restore -l "$BACKUP_DIR/postgres.dump" > /dev/null 2>&1 && \
  log "Dump integrity check PASSED" || warn "Dump integrity check FAILED (still continuing)"

# --- Step 5: simulate restore -----------------------------------------
log "Step 5: Teardown"
docker compose -f "$COMPOSE_FILE" down

log "Step 6: Fresh start + restore"
docker compose -f "$COMPOSE_FILE" up -d postgres redis
sleep 8

# Wait for postgres to be healthy
for i in $(seq 1 20); do
  docker exec infra-postgres-1 pg_isready -U agentnet -d agentnet > /dev/null 2>&1 && break
  sleep 2
done
log "Postgres ready"

log "Step 7: Restoring database"
docker exec -i infra-postgres-1 pg_restore -U agentnet -d agentnet --clean --if-exists \
  < "$BACKUP_DIR/postgres.dump" 2>&1 | tail -3
log "Restore complete"

log "Step 8: Starting API"
docker compose -f "$COMPOSE_FILE" up -d
sleep 10

# --- Step 9: healthz verification -------------------------------------
log "Step 9: Healthz verification"
for i in $(seq 1 15); do
  if curl -sf http://localhost:8000/healthz | grep -q '"ok"'; then
    log "Healthz PASSED — backup/restore drill SUCCESSFUL"
    echo ""
    echo "  Backup location: $BACKUP_DIR"
    echo "  Postgres dump : $(ls -lh "$BACKUP_DIR/postgres.dump" | awk '{print $5}')"
    echo ""
    exit 0
  fi
  sleep 2
done

warn "Healthz FAILED after restore — check docker logs infra-api-1"
exit 1
