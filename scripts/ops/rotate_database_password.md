# Rotate Database Password Runbook

## Purpose

Rotate the production PostgreSQL password with a backup, maintenance window, validation, and rollback path.

## Steps

1. Enter maintenance window.
2. Run:

```powershell
./scripts/backup/postgres_backup.ps1
```

3. Stop API:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production stop api
```

4. Change the Postgres user password.
5. Update `POSTGRES_PASSWORD` and `DATABASE_URL` in `infra/.env.production`.
6. Start API and verify:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up -d api
curl.exe http://localhost/healthz
```

## Rollback

Restore the previous password and `.env.production`, restart API, and use `docs/backup-restore.md` if data recovery is required.
