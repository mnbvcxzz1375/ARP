$ErrorActionPreference = "Stop"

$Help = $false
$DryRun = $false
$DatabaseUrl = $env:DATABASE_URL
$BackupDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { "backups/postgres" }
$RetentionDays = if ($env:RETENTION_DAYS) { [int]$env:RETENTION_DAYS } else { 14 }

function Show-Help {
    Write-Output @"
Usage: ./scripts/backup/postgres_backup.ps1 [--dry-run] [--database-url <url>] [--backup-dir <dir>] [--retention-days <days>]

Creates a PostgreSQL custom-format backup and SHA-256 checksum.

Options:
  --help                 Show this help.
  --dry-run              Print the planned actions without running pg_dump.
  --database-url <url>   PostgreSQL connection URL. Defaults to DATABASE_URL.
  --backup-dir <dir>     Destination directory. Defaults to BACKUP_DIR or backups/postgres.
  --retention-days <n>   Delete local backups older than n days. Defaults to RETENTION_DAYS or 14.
"@
}

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        "--help" { $Help = $true }
        "-h" { $Help = $true }
        "--dry-run" { $DryRun = $true }
        "--database-url" { $i++; $DatabaseUrl = $args[$i] }
        "--backup-dir" { $i++; $BackupDir = $args[$i] }
        "--retention-days" { $i++; $RetentionDays = [int]$args[$i] }
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

if ($Help) {
    Show-Help
    exit 0
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$backupPath = Join-Path $BackupDir "agentnet_$timestamp.dump"
$checksumPath = "$backupPath.sha256"

if ($DryRun) {
    Write-Output "DRY RUN: would create backup directory: $BackupDir"
    Write-Output "DRY RUN: would run pg_dump --format=custom --file $backupPath <DATABASE_URL>"
    Write-Output "DRY RUN: would write checksum: $checksumPath"
    Write-Output "DRY RUN: would prune backups older than $RetentionDays days"
    exit 0
}

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw "DATABASE_URL is required. Set DATABASE_URL or pass --database-url."
}

$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDump) {
    throw "pg_dump was not found on PATH."
}

New-Item -ItemType Directory -Force $BackupDir | Out-Null
Invoke-Checked -FilePath $pgDump.Source -Arguments @("--format=custom", "--file", $backupPath, $DatabaseUrl)

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $backupPath
"$($hash.Hash.ToLowerInvariant())  $(Split-Path -Leaf $backupPath)" | Set-Content -LiteralPath $checksumPath -Encoding ASCII

if ($RetentionDays -gt 0) {
    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    Get-ChildItem -LiteralPath $BackupDir -File -Filter "agentnet_*.dump*" |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force
}

Write-Output "Backup created: $backupPath"
Write-Output "Checksum created: $checksumPath"
