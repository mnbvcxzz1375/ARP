# Postgres Backup Scripts

These scripts create and restore PostgreSQL custom-format dumps for the single-node Docker Compose deployment.

## PowerShell

```powershell
./scripts/backup/postgres_backup.ps1 --help
./scripts/backup/postgres_backup.ps1 --dry-run
./scripts/backup/postgres_restore.ps1 --help
./scripts/backup/postgres_restore.ps1 --dry-run
```

## Bash

```bash
./scripts/backup/postgres_backup.sh --help
./scripts/backup/postgres_backup.sh --dry-run
./scripts/backup/postgres_restore.sh --help
./scripts/backup/postgres_restore.sh --dry-run
```

Real restore requires `--file`, a matching `.sha256`, `DATABASE_URL`, and `--yes`.
