# Backup and Restore

This document covers PostgreSQL backup, restore, verification, and drill
procedures for a single-node AgentNet Docker Compose deployment.

## Purpose

PostgreSQL is the long-term source of truth for AgentNet: users, API key
hashes, agents, tasks, messages, approvals, and audit logs. Redis only holds
short-lived state (pending queues, presence, rate limits) and is not part of a
long-term backup strategy in this cycle.

## Prerequisites

- `pg_dump` and `pg_restore` installed, ideally matching the production
  Postgres major version.
- `DATABASE_URL` set to the target database.
- For production runs: enter a maintenance window first and confirm a recent
  backup exists.

## Backup

PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://agentnet:CHANGE_ME@localhost:5432/agentnet"
./scripts/backup/postgres_backup.ps1
```

Bash:

```bash
export DATABASE_URL="postgresql://agentnet:CHANGE_ME@localhost:5432/agentnet"
./scripts/backup/postgres_backup.sh
```

Default outputs:

```text
backups/postgres/agentnet_YYYYMMDD_HHMMSS.dump
backups/postgres/agentnet_YYYYMMDD_HHMMSS.dump.sha256
```

Dry-run:

```powershell
./scripts/backup/postgres_backup.ps1 --dry-run
```

## Daily scheduled task example

Windows Task Scheduler can run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File E:\AgentNet\scripts\backup\postgres_backup.ps1
```

Linux cron example:

```cron
15 2 * * * cd /opt/agentnet && DATABASE_URL='postgresql://agentnet:***@postgres:5432/agentnet' ./scripts/backup/postgres_backup.sh >> /var/log/agentnet-backup.log 2>&1
```

## Restore

Restore verifies the checksum, takes a pre-restore snapshot, and then runs
`pg_restore --clean --if-exists`.

PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://agentnet:CHANGE_ME@localhost:5432/agentnet"
./scripts/backup/postgres_restore.ps1 --file backups/postgres/agentnet_YYYYMMDD_HHMMSS.dump --yes
```

Bash:

```bash
export DATABASE_URL="postgresql://agentnet:CHANGE_ME@localhost:5432/agentnet"
./scripts/backup/postgres_restore.sh --file backups/postgres/agentnet_YYYYMMDD_HHMMSS.dump --yes
```

Dry-run:

```powershell
./scripts/backup/postgres_restore.ps1 --dry-run
```

## Production restore sequence

1. Announce the maintenance window and pause external traffic.
2. Stop the API container:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production stop api
```

3. Run the restore script.
4. Check the migration revision:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic current
```

5. Start the API:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up -d api
```

6. Check health:

```powershell
curl.exe http://localhost/healthz
```

## Monthly restore drill

1. Copy the latest `.dump` and `.sha256` to an isolated test environment.
2. Start an empty Postgres.
3. Set the test `DATABASE_URL`.
4. Run a restore dry-run.
5. Run the real restore.
6. Run `alembic current` and `/healthz`.
7. Spot-check the user, agent, task, message, approval, and audit log tables.
8. Record the drill result, durations, failures, and improvements.

## Common failure causes

- `pg_dump was not found on PATH`: PostgreSQL client tools are not installed.
- checksum mismatch: the backup file is corrupted or the `.sha256` does not
  match; restoring is forbidden.
- authentication failed: the `DATABASE_URL` user, password, or host is wrong.
- restore refused: a real restore requires an explicit `--yes`.

## Security notes

- A `.dump` may contain sensitive business data and hashes; protect it at the
  same level as production data.
- Never commit a plaintext `DATABASE_URL` to the repository.
- Restrict the backup directory to the operator user.
- A pre-restore snapshot is not a substitute for a real backup, but it allows
  an emergency rollback after a bad restore.
