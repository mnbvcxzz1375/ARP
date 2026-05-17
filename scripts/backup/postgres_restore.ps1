$ErrorActionPreference = "Stop"

$Help = $false
$DryRun = $false
$Yes = $false
$File = ""
$DatabaseUrl = $env:DATABASE_URL
$SnapshotDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { "backups/postgres" }

function Show-Help {
    Write-Output @"
Usage: ./scripts/backup/postgres_restore.ps1 --file <backup.dump> --yes [--database-url <url>]

Restores a PostgreSQL custom-format backup with checksum verification.

Options:
  --help                 Show this help.
  --dry-run              Print the planned checks and restore actions.
  --yes                  Required for a real restore.
  --file <backup.dump>   Backup file to restore.
  --database-url <url>   PostgreSQL connection URL. Defaults to DATABASE_URL.
  --snapshot-dir <dir>   Directory for the pre-restore snapshot.
"@
}

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        "--help" { $Help = $true }
        "-h" { $Help = $true }
        "--dry-run" { $DryRun = $true }
        "--yes" { $Yes = $true }
        "--file" { $i++; $File = $args[$i] }
        "--database-url" { $i++; $DatabaseUrl = $args[$i] }
        "--snapshot-dir" { $i++; $SnapshotDir = $args[$i] }
        default { throw "Unknown argument: $($args[$i])" }
    }
}

function Invoke-Checked {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

function Test-Checksum {
    param([string]$BackupFile)
    $checksumFile = "$BackupFile.sha256"
    if (-not (Test-Path -LiteralPath $checksumFile)) {
        throw "Checksum file not found: $checksumFile"
    }
    $expected = ((Get-Content -LiteralPath $checksumFile -Raw).Trim() -split "\s+")[0].ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $BackupFile).Hash.ToLowerInvariant()
    if ($expected -ne $actual) {
        throw "Checksum mismatch for $BackupFile"
    }
}

if ($Help) {
    Show-Help
    exit 0
}

if ($DryRun) {
    Write-Output "DRY RUN: would require backup file: $File"
    Write-Output "DRY RUN: would verify <backup>.sha256 checksum when --file is provided"
    Write-Output "DRY RUN: would create pre-restore snapshot in: $SnapshotDir"
    Write-Output "DRY RUN: would run pg_restore --clean --if-exists --dbname <DATABASE_URL> <backup>"
    Write-Output "DRY RUN: would run alembic current and /healthz verification after service restart"
    exit 0
}

if (-not $Yes) {
    throw "Refusing to restore without --yes."
}
if ([string]::IsNullOrWhiteSpace($File)) {
    throw "--file is required for restore."
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw "DATABASE_URL is required. Set DATABASE_URL or pass --database-url."
}
if (-not (Test-Path -LiteralPath $File)) {
    throw "Backup file not found: $File"
}

Test-Checksum -BackupFile $File

$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
$pgRestore = Get-Command pg_restore -ErrorAction SilentlyContinue
if (-not $pgDump) {
    throw "pg_dump was not found on PATH."
}
if (-not $pgRestore) {
    throw "pg_restore was not found on PATH."
}

New-Item -ItemType Directory -Force $SnapshotDir | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$snapshot = Join-Path $SnapshotDir "agentnet_pre_restore_$timestamp.dump"
Invoke-Checked -FilePath $pgDump.Source -Arguments @("--format=custom", "--file", $snapshot, $DatabaseUrl)
Invoke-Checked -FilePath $pgRestore.Source -Arguments @("--clean", "--if-exists", "--dbname", $DatabaseUrl, $File)

Write-Output "Restore completed from: $File"
Write-Output "Pre-restore snapshot created: $snapshot"
