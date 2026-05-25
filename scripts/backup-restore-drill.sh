#!/usr/bin/env bash
# backup-restore-drill.sh
# Full backup → teardown → restore → healthz drill for AgentNet.
# Fail-closed: every critical step must succeed; no silent fallbacks.
#
# Usage: AGENTNET_API_KEY=<key> bash scripts/backup-restore-drill.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups/$(date +%Y%m%d-%H%M%S)"
COMPOSE_FILE="$PROJECT_DIR/infra/docker-compose.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${RED}[!]${NC} $*"; }
info() { echo -e "${YELLOW}[i]${NC} $*"; }

API_KEY="${AGENTNET_API_KEY:?ERROR: AGENTNET_API_KEY environment variable must be set}"

# --- Helper: parse JSON field with python3 (portable, no jq dependency) ---
json_field() {
  local field="$1"
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d[sys.argv[1]])" "$field"
}

# --- Step 0: pre-flight -----------------------------------------------
log "Step 0: Pre-flight checks"
mkdir -p "$BACKUP_DIR"
docker ps --format '{{.Names}}' | grep -q infra-api-1  || { warn "API container not running. Start via docker compose first."; exit 1; }

# Verify healthz returns {"status":"alive"} using JSON parsing
HEALTHZ_BODY=$(curl -sf http://localhost:8000/healthz) || { warn "API healthz unreachable."; exit 1; }
HEALTHZ_STATUS=$(echo "$HEALTHZ_BODY" | json_field "status") || { warn "Failed to parse healthz response: $HEALTHZ_BODY"; exit 1; }
if [ "$HEALTHZ_STATUS" != "alive" ]; then
  warn "API healthz returned unexpected status: $HEALTHZ_STATUS"; exit 1;
fi
log "Pre-flight OK — backup dir: $BACKUP_DIR"

# --- Step 1: backup PostgreSQL ----------------------------------------
log "Step 1: Backing up PostgreSQL"
docker exec infra-postgres-1 pg_dump -U agentnet -d agentnet -Fc \
  > "$BACKUP_DIR/postgres.dump"
DUMP_SIZE=$(wc -c < "$BACKUP_DIR/postgres.dump")
if [ "$DUMP_SIZE" -eq 0 ]; then
  warn "PostgreSQL dump is 0 bytes"; exit 1;
fi
log "PostgreSQL dump: $DUMP_SIZE bytes"

# --- Step 2: backup Redis (RDB snapshot) ------------------------------
log "Step 2: Backing up Redis"

# Detect AOF config — failure to query Redis is fatal, not a silent default
AOF_ENABLED=$(docker exec infra-redis-1 redis-cli CONFIG GET appendonly 2>/dev/null | tail -1) \
  || { warn "Failed to query Redis CONFIG GET appendonly. Is Redis running?"; exit 1; }

# Trigger BGSAVE and wait for it to finish
docker exec infra-redis-1 redis-cli BGSAVE > /dev/null \
  || { warn "redis-cli BGSAVE failed."; exit 1; }

# Poll until BGSAVE completes and verify it succeeded
BGSAVE_DONE=false
for i in $(seq 1 30); do
  INFO_PERSIST=$(docker exec infra-redis-1 redis-cli INFO persistence 2>/dev/null) \
    || { warn "Failed to query Redis INFO persistence."; exit 1; }
  IN_PROGRESS=$(echo "$INFO_PERSIST" | grep '^rdb_bgsave_in_progress:' | tr -d '\r' | cut -d: -f2)
  BGSAVE_STATUS=$(echo "$INFO_PERSIST" | grep '^rdb_last_bgsave_status:' | tr -d '\r' | cut -d: -f2)
  if [ "$IN_PROGRESS" = "0" ]; then
    if [ "$BGSAVE_STATUS" = "ok" ]; then
      BGSAVE_DONE=true
      break
    else
      warn "BGSAVE finished with status: ${BGSAVE_STATUS:-unknown}"; exit 1;
    fi
  fi
  sleep 1
done
if [ "$BGSAVE_DONE" = "false" ]; then
  warn "BGSAVE did not complete within 30 seconds."; exit 1;
fi

# Copy RDB dump — always attempt first, even if AOF is enabled
if docker cp infra-redis-1:/data/dump.rdb "$BACKUP_DIR/redis-dump.rdb" 2>/dev/null; then
  RDB_SIZE=$(wc -c < "$BACKUP_DIR/redis-dump.rdb")
  if [ "$RDB_SIZE" -eq 0 ]; then
    warn "Redis dump.rdb is 0 bytes."; exit 1;
  fi
  log "Redis RDB snapshot captured: $RDB_SIZE bytes"
elif [ "$AOF_ENABLED" = "yes" ]; then
  # AOF mode with no RDB: try Redis 7 appendonlydir first, then legacy single file
  info "Redis is AOF-only (appendonly=yes, no RDB). Attempting AOF backup."
  if docker cp infra-redis-1:/data/appendonlydir/. "$BACKUP_DIR/redis-appendonlydir" 2>/dev/null; then
    AOF_SIZE=$(du -sb "$BACKUP_DIR/redis-appendonlydir" | cut -f1)
    if [ "$AOF_SIZE" -eq 0 ]; then
      warn "Redis appendonlydir copied but is empty."; exit 1;
    fi
    log "Redis AOF backup captured (appendonlydir): $AOF_SIZE bytes"
  elif docker cp infra-redis-1:/data/appendonly.aof "$BACKUP_DIR/redis-appendonly.aof" 2>/dev/null; then
    AOF_SIZE=$(wc -c < "$BACKUP_DIR/redis-appendonly.aof")
    if [ "$AOF_SIZE" -eq 0 ]; then
      warn "Redis appendonly.aof is 0 bytes."; exit 1;
    fi
    log "Redis AOF backup captured: $AOF_SIZE bytes"
  else
    warn "Redis AOF enabled but no appendonlydir/ or appendonly.aof found in /data."
    warn "Redis persistence files are missing — cannot proceed."
    exit 1;
  fi
else
  warn "Redis dump.rdb not found and AOF is not enabled."
  warn "Redis persistence may be disabled or the data directory is empty."
  exit 1;
fi

# --- Step 3: record agents/tasks/users count --------------------------
log "Step 3: Recording backup metadata"

# Fetch API key count — failure is fatal (validates API connectivity and auth)
APIKEY_JSON=$(curl -sf http://localhost:8000/v1/auth/api-keys \
  -H "Authorization: Bearer $API_KEY") || { warn "Failed to fetch API keys metadata. Check API key and connectivity."; exit 1; }
APIKEY_TOTAL=$(echo "$APIKEY_JSON" | json_field "total") || { warn "Failed to parse API keys response."; exit 1; }
echo "API keys: $APIKEY_TOTAL" > "$BACKUP_DIR/metadata.txt"

# Fetch task count — failure is fatal
TASKS_JSON=$(curl -sf http://localhost:8000/v1/tasks \
  -H "Authorization: Bearer $API_KEY") || { warn "Failed to fetch tasks metadata."; exit 1; }
TASKS_TOTAL=$(echo "$TASKS_JSON" | json_field "total") || { warn "Failed to parse tasks response."; exit 1; }
echo "Tasks: $TASKS_TOTAL" >> "$BACKUP_DIR/metadata.txt"

log "Backup metadata: $(cat "$BACKUP_DIR/metadata.txt")"

# --- Step 4: verify the dump is restorable ----------------------------
log "Step 4: Verifying dump integrity"
if pg_restore -l "$BACKUP_DIR/postgres.dump" > /dev/null 2>&1; then
  log "Dump integrity check PASSED"
else
  warn "Dump integrity check FAILED — pg_restore -l returned error"
  warn "The backup file is corrupt or incomplete. Aborting drill."
  exit 1;
fi

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
  HEALTHZ_BODY=$(curl -sf http://localhost:8000/healthz 2>/dev/null) || { sleep 2; continue; }
  HEALTHZ_STATUS=$(echo "$HEALTHZ_BODY" | json_field "status") || { sleep 2; continue; }
  if [ "$HEALTHZ_STATUS" = "alive" ]; then
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
