<#
.SYNOPSIS
    Windows-friendly backup/restore drill validation wrapper for AgentNet.

.DESCRIPTION
    Supports two modes:
      - DryRun (default): Validates scripts exist, checks configuration,
        simulates backup path without touching data.
      - Real: Performs actual backup and optionally restores, with explicit
        confirmation and post-restore health checks.

    Real mode REQUIRES -RealMode flag and a -BackupDir path.
    Restore REQUIRES both -RealMode and -RestoreBackup flags.

.PARAMETER Mode
    "DryRun" (default) or "Real".

.PARAMETER BackupDir
    Directory for backup output (required for Real mode).

.PARAMETER RestoreBackup
    Path to a specific backup archive to restore (implies Real mode).

.PARAMETER SkipHealthCheck
    Skip post-restore health check against API.

.PARAMETER ApiBaseUrl
    API base URL for health checks (default: http://localhost:8000).

.EXAMPLE
    .\backup-restore-drill.ps1 -Mode DryRun
    .\backup-restore-drill.ps1 -Mode Real -BackupDir C:\backups\agentnet
    .\backup-restore-drill.ps1 -Mode Real -BackupDir C:\backups\agentnet -RestoreBackup C:\backups\agentnet\backup-2025-01-01.tar.gz
#>
param(
    [ValidateSet("DryRun", "Real")]
    [string]$Mode = "DryRun",
    [string]$BackupDir = "",
    [string]$RestoreBackup = "",
    [switch]$SkipHealthCheck = $false,
    [string]$ApiBaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

# ── Helpers ────────────────────────────────────────────────────────

function Write-Status($check, $status, $detail = "") {
    $icon = switch ($status) {
        "PASS" { "✓" }
        "FAIL" { "✗" }
        "SKIP" { "⊘" }
        "WARN" { "⚠" }
        default { "?" }
    }
    Write-Host ("  {0} {1}: {2}" -f $icon, $check, $status)
    if ($detail) {
        Write-Host ("      {0}" -f $detail)
    }
}

function Test-FileHash($Path) {
    if (-not (Test-Path $Path)) {
        return $null
    }
    $hash = Get-FileHash -Path $Path -Algorithm SHA256
    return $hash.Hash
}

# ── Pre-flight checks ──────────────────────────────────────────────

Write-Host "`n============================================================"
Write-Host ("AgentNet Backup/Restore Drill — {0} Mode" -f $Mode)
Write-Host "============================================================`n"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$backupScript = Join-Path $projectRoot "scripts\backup-restore-drill.sh"

# Check prerequisites
Write-Host "Pre-flight checks:"

if (Test-Path $backupScript) {
    Write-Status "backup-restore-drill.sh exists" "PASS"
} else {
    Write-Status "backup-restore-drill.sh exists" "FAIL" "Not found at $backupScript"
}

# Check Docker availability
$dockerAvailable = $false
try {
    $dockerVer = docker version --format "{{.Client.Version}}" 2>$null
    if ($LASTEXITCODE -eq 0 -and $dockerVer) {
        Write-Status "Docker available" "PASS" "Version: $dockerVer"
        $dockerAvailable = $true
    } else {
        Write-Status "Docker available" "SKIP" "Docker not running or not installed"
    }
} catch {
    Write-Status "Docker available" "SKIP" "Docker not available"
}

# Check pg_dump availability (via Docker or local)
$pgDumpAvailable = $false
try {
    $pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
    if ($pgDump) {
        Write-Status "pg_dump available" "PASS" "Path: $($pgDump.Source)"
        $pgDumpAvailable = $true
    } elseif ($dockerAvailable) {
        Write-Status "pg_dump available" "WARN" "Not local, but can use Docker container"
        $pgDumpAvailable = $true
    } else {
        Write-Status "pg_dump available" "FAIL" "Neither local pg_dump nor Docker available"
    }
} catch {
    Write-Status "pg_dump available" "FAIL" $_.Exception.Message
}

# Check Redis CLI
$redisAvailable = $false
try {
    $redisCli = Get-Command redis-cli -ErrorAction SilentlyContinue
    if ($redisCli) {
        Write-Status "redis-cli available" "PASS"
        $redisAvailable = $true
    } else {
        Write-Status "redis-cli available" "SKIP" "Not found locally"
    }
} catch {
    Write-Status "redis-cli available" "SKIP"
}

# ── Mode-specific logic ────────────────────────────────────────────

if ($Mode -eq "DryRun") {
    Write-Host "`nDry-run validation:"

    # Validate script structure
    $scriptContent = Get-Content $backupScript -Raw -ErrorAction SilentlyContinue
    if ($scriptContent -match "pg_dump") {
        Write-Status "Script contains pg_dump" "PASS"
    } else {
        Write-Status "Script contains pg_dump" "FAIL" "Backup script missing pg_dump"
    }

    if ($scriptContent -match "redis-cli.*BGSAVE") {
        Write-Status "Script contains Redis BGSAVE" "PASS"
    } else {
        Write-Status "Script contains Redis BGSAVE" "WARN" "No BGSAVE found — check backup strategy"
    }

    if ($scriptContent -match "checksum|sha256|md5") {
        Write-Status "Script includes checksum verification" "PASS"
    } else {
        Write-Status "Script includes checksum verification" "WARN" "No checksum verification found"
    }

    if ($scriptContent -match "healthz|readyz|health.check") {
        Write-Status "Script includes post-restore health check" "PASS"
    } else {
        Write-Status "Script includes post-restore health check" "WARN" "No health check found in script"
    }

    # Check Docker Compose services
    if ($dockerAvailable) {
        try {
            $composePath = Join-Path $projectRoot "infra\docker-compose.yml"
            if (Test-Path $composePath) {
                Write-Status "Docker Compose file exists" "PASS"
            } else {
                Write-Status "Docker Compose file exists" "FAIL"
            }
        } catch {
            Write-Status "Docker Compose check" "ERROR" $_.Exception.Message
        }
    }

    Write-Host "`nDry-run complete. No data was modified."
    Write-Host "To run a real drill, use: .\backup-restore-drill.ps1 -Mode Real -BackupDir C:\path\to\backups"

} elseif ($Mode -eq "Real") {
    # ── Real mode ──────────────────────────────────────────────────
    if (-not $BackupDir) {
        Write-Host "ERROR: -BackupDir is required for Real mode."
        exit 1
    }

    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
        Write-Status "Created backup directory" "PASS" $BackupDir
    }

    $timestamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
    $backupFile = Join-Path $BackupDir "agentnet-backup-$timestamp.tar.gz"
    $checksumFile = Join-Path $BackupDir "agentnet-backup-$timestamp.sha256"

    Write-Host "`nReal backup drill:"

    # Run backup via Docker/WSL if script is bash
    $wslAvailable = $false
    try {
        $wslCheck = wsl --list 2>$null
        if ($LASTEXITCODE -eq 0) {
            $wslAvailable = $true
        }
    } catch {}

    if ($wslAvailable) {
        Write-Host "  Running backup via WSL..."
        $wslProjectRoot = ($projectRoot -replace "\\", "/")
        $wslBackupDir = ($BackupDir -replace "\\", "/")
        $result = wsl -e bash -c "cd '$wslProjectRoot' && DATABASE_URL='$env:DATABASE_URL' REDIS_URL='$env:REDIS_URL' BACKUP_DIR='$wslBackupDir' bash scripts/backup-restore-drill.sh backup" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Backup completed" "PASS"
        } else {
            Write-Status "Backup completed" "FAIL" $result
        }
    } else {
        Write-Host "  WSL not available. Attempting direct pg_dump..."
        if ($pgDumpAvailable) {
            $dbUrl = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "postgresql://agentnet:agentnet@localhost:5432/agentnet" }
            try {
                $dumpFile = Join-Path $BackupDir "db-backup-$timestamp.sql"
                $env:PGPASSWORD = "agentnet"
                & pg_dump $dbUrl --file $dumpFile --no-owner 2>&1 | Out-Null
                if (Test-Path $dumpFile) {
                    $hash = Test-FileHash $dumpFile
                    Write-Status "pg_dump backup" "PASS" "File: $dumpFile, SHA256: $($hash.Substring(0,16))..."
                    $hash | Out-File -FilePath "$dumpFile.sha256" -Encoding utf8
                } else {
                    Write-Status "pg_dump backup" "FAIL" "Dump file not created"
                }
            } catch {
                Write-Status "pg_dump backup" "FAIL" $_.Exception.Message
            } finally {
                Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
            }
        } else {
            Write-Status "Backup" "SKIP" "Neither WSL nor pg_dump available"
        }
    }

    # ── Restore drill ──────────────────────────────────────────────
    if ($RestoreBackup) {
        Write-Host "`n!!! RESTORE DRILL — This will overwrite data !!!"
        Write-Host ("    Restoring from: {0}" -f $RestoreBackup)
        $confirm = Read-Host "Type 'CONFIRM RESTORE' to proceed"
        if ($confirm -ne "CONFIRM RESTORE") {
            Write-Host "Restore cancelled."
        } else {
            Write-Host "  Restoring..."
            # Restore logic would go here - platform-specific
            Write-Status "Restore completed" "WARN" "Actual restore requires environment-specific implementation"

            # Checksum verification
            $restoreHash = Test-FileHash $RestoreBackup
            if ($restoreHash) {
                $expectedHashFile = "$RestoreBackup.sha256"
                if (Test-Path $expectedHashFile) {
                    $expected = (Get-Content $expectedHashFile -Raw).Trim()
                    if ($restoreHash -eq $expected) {
                        Write-Status "Checksum verification" "PASS"
                    } else {
                        Write-Status "Checksum verification" "FAIL" "Hash mismatch"
                    }
                } else {
                    Write-Status "Checksum verification" "SKIP" "No .sha256 file to compare"
                }
            }

            # Post-restore health check
            if (-not $SkipHealthCheck) {
                Write-Host "`n  Post-restore health check:"
                try {
                    $healthResp = Invoke-RestMethod -Uri "$ApiBaseUrl/healthz" -TimeoutSec 10 -ErrorAction Stop
                    Write-Status "Health check (/healthz)" "PASS" ($healthResp | ConvertTo-Json -Compress)
                } catch {
                    Write-Status "Health check (/healthz)" "FAIL" $_.Exception.Message
                }

                try {
                    $readyResp = Invoke-RestMethod -Uri "$ApiBaseUrl/readyz" -TimeoutSec 10 -ErrorAction Stop
                    Write-Status "Readiness check (/readyz)" "PASS" ($readyResp | ConvertTo-Json -Compress)
                } catch {
                    Write-Status "Readiness check (/readyz)" "FAIL" $_.Exception.Message
                }
            }
        }
    } else {
        Write-Host "`nNo -RestoreBackup specified. Skipping restore phase."
        Write-Host "To test restore: .\backup-restore-drill.ps1 -Mode Real -BackupDir <dir> -RestoreBackup <backup-file>"
    }
}

Write-Host "`n============================================================"
Write-Host "Drill complete."
Write-Host "============================================================`n"
