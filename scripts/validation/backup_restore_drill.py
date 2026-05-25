#!/usr/bin/env python3
"""AgentNet backup/restore drill — isolated recovery validation.

Performs a real pg_dump from the running infra-postgres-1 container,
restores into a temporary postgres:16-alpine container, and verifies
the restored data has tables in the public schema.

Usage:
    python backup_restore_drill.py --backup-dir <directory>

Requirements:
    - Docker must be available and running
    - infra-postgres-1 container must be running (from docker-compose)

Exit codes:
    0  All steps PASSED
    1  Any step FAILED — no dry-run pass-through
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

POSTGRES_CONTAINER = "infra-postgres-1"
POSTGRES_USER = "agentnet"
POSTGRES_DB = "agentnet"
TEMP_CONTAINER_PREFIX = "agentnet-restore-drill"


def _run(cmd: list[str], check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check)


def _status(check: str, status: str, detail: str = ""):
    icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "⊘"}.get(status, "?")
    print(f"  {icon} {check}: {status}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"      {line}")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    # Parse args
    backup_dir = ""
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--backup-dir" and i < len(sys.argv) - 1:
            backup_dir = sys.argv[i + 1]

    if not backup_dir:
        print("ERROR: --backup-dir is required")
        print("Usage: python backup_restore_drill.py --backup-dir <directory>")
        sys.exit(1)

    backup_path = Path(backup_dir).resolve()
    backup_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print("AgentNet Backup/Restore Drill")
    print(f"{'='*60}\n")

    all_ok = True

    # ── Step 1: Docker availability ──────────────────────────────────
    print("Step 1: Docker availability")
    try:
        r = _run(["docker", "version", "--format", "{{.Client.Version}}"])
        _status("Docker available", "PASS", f"Version: {r.stdout.strip()}")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        _status("Docker available", "FAIL", str(e))
        all_ok = False
    if not all_ok:
        _fail_exit()

    # ── Step 2: infra-postgres-1 running ─────────────────────────────
    print("\nStep 2: Source container running")
    try:
        r = _run(["docker", "inspect", "-f", "{{.State.Running}}", POSTGRES_CONTAINER])
        if r.stdout.strip().lower() == "true":
            _status(f"{POSTGRES_CONTAINER} running", "PASS")
        else:
            _status(f"{POSTGRES_CONTAINER} running", "FAIL",
                    f"Container exists but not running (State.Running={r.stdout.strip()})")
            all_ok = False
    except subprocess.CalledProcessError:
        _status(f"{POSTGRES_CONTAINER} running", "FAIL",
            f"Container '{POSTGRES_CONTAINER}' not found. "
            "Start the stack first: docker compose -f infra/docker-compose.yml up -d")
        all_ok = False
    if not all_ok:
        _fail_exit()

    # ── Step 3: pg_dump ──────────────────────────────────────────────
    print("\nStep 3: pg_dump from source")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    dump_file = backup_path / f"agentnet-drill-{timestamp}.dump"

    # Must use binary capture_output — -Fc produces binary output that
    # text=True would corrupt with UTF-8 decode errors.
    try:
        r = subprocess.run(
            ["docker", "exec", POSTGRES_CONTAINER,
             "pg_dump", "-U", POSTGRES_USER, "-d", POSTGRES_DB, "-Fc"],
            capture_output=True, timeout=120,
        )
        if r.returncode != 0:
            _status("pg_dump", "FAIL", r.stderr.decode("utf-8", errors="replace").strip())
            all_ok = False
        else:
            dump_file.write_bytes(r.stdout)
            _status("pg_dump", "PASS", f"Dump written to {dump_file}")
    except subprocess.TimeoutExpired:
        _status("pg_dump", "FAIL", "pg_dump timed out after 120s")
        all_ok = False
    except Exception as e:
        _status("pg_dump", "FAIL", str(e))
        all_ok = False

    if not all_ok:
        _fail_exit()

    # ── Step 4: Verify dump file ─────────────────────────────────────
    print("\nStep 4: Dump file verification")
    if not dump_file.exists():
        _status("Dump file exists", "FAIL", f"File not found: {dump_file}")
        all_ok = False
    elif dump_file.stat().st_size == 0:
        _status("Dump file non-empty", "FAIL", "Dump file is 0 bytes")
        all_ok = False
    else:
        size_kb = dump_file.stat().st_size / 1024
        sha256 = _sha256_file(dump_file)
        _status("Dump file non-empty", "PASS", f"Size: {size_kb:.1f} KB, SHA256: {sha256[:16]}...")

    if not all_ok:
        _fail_exit()

    # ── Step 5: Start temporary postgres container ───────────────────
    print("\nStep 5: Temporary restore container")
    suffix = f"{os.getpid()}-{int(time.time())}"
    temp_container = f"{TEMP_CONTAINER_PREFIX}-{suffix}"

    try:
        r = _run([
            "docker", "run", "-d",
            "--name", temp_container,
            "-e", f"POSTGRES_USER={POSTGRES_USER}",
            "-e", f"POSTGRES_DB={POSTGRES_DB}",
            "-e", "POSTGRES_PASSWORD=drill-test-password",
            "postgres:16-alpine",
        ], timeout=60)
        if r.returncode != 0:
            _status("Start temp container", "FAIL", r.stderr.strip())
            all_ok = False
        else:
            _status("Start temp container", "PASS", f"Container: {temp_container}")
    except Exception as e:
        _status("Start temp container", "FAIL", str(e))
        all_ok = False

    if not all_ok:
        _cleanup(temp_container)
        _fail_exit()

    # Wait for pg_isready
    ready = False
    for attempt in range(30):
        try:
            r = _run(["docker", "exec", temp_container, "pg_isready", "-U", POSTGRES_USER], timeout=10)
            if r.returncode == 0:
                ready = True
                break
        except Exception:
            pass
        time.sleep(1)

    if ready:
        _status("Temp container ready", "PASS", "pg_isready succeeded")
    else:
        _status("Temp container ready", "FAIL", "pg_isready did not succeed within 30s")
        _cleanup(temp_container)
        _fail_exit()

    # ── Step 6: Copy dump into temp container and restore ────────────
    print("\nStep 6: pg_restore into temp container")
    try:
        # Copy dump file into container
        r = _run(["docker", "cp", str(dump_file), f"{temp_container}:/tmp/restore.dump"], timeout=30)
        if r.returncode != 0:
            _status("Copy dump to container", "FAIL", r.stderr.strip())
            all_ok = False
        else:
            _status("Copy dump to container", "PASS")

            # Create the database (it may already exist from POSTGRES_DB env)
            _run(["docker", "exec", temp_container,
                  "psql", "-U", POSTGRES_USER, "-d", POSTGRES_DB,
                  "-c", "SELECT 1"], timeout=10)

            # Restore
            r = _run([
                "docker", "exec", temp_container,
                "pg_restore", "-U", POSTGRES_USER, "-d", POSTGRES_DB,
                "-v", "--no-owner", "--no-privileges",
                "/tmp/restore.dump",
            ], timeout=120)
            # pg_restore may return warnings (exit code 1) for already-existing objects
            # but real errors are in stderr with "ERROR:"
            stderr_text = r.stderr.strip() if r.stderr else ""
            error_lines = [l for l in stderr_text.splitlines()
                          if "ERROR:" in l and "already exists" not in l.lower()]
            if error_lines:
                _status("pg_restore", "FAIL", "\n".join(error_lines[:5]))
                all_ok = False
            else:
                _status("pg_restore", "PASS",
                        "Restored successfully" + (" (with warnings)" if stderr_text else ""))
    except subprocess.TimeoutExpired:
        _status("pg_restore", "FAIL", "pg_restore timed out after 120s")
        all_ok = False
    except Exception as e:
        _status("pg_restore", "FAIL", str(e))
        all_ok = False

    if not all_ok:
        _cleanup(temp_container)
        _fail_exit()

    # ── Step 7: Verify restored data ─────────────────────────────────
    print("\nStep 7: Restored data verification")
    try:
        r = _run([
            "docker", "exec", temp_container,
            "psql", "-U", POSTGRES_USER, "-d", POSTGRES_DB, "-t", "-A",
            "-c", "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';",
        ], timeout=15)
        if r.returncode != 0:
            _status("Table count query", "FAIL", r.stderr.strip())
            all_ok = False
        else:
            table_count = int(r.stdout.strip())
            if table_count > 0:
                _status("Public schema tables", "PASS", f"Found {table_count} table(s) in public schema")
            else:
                _status("Public schema tables", "FAIL",
                        "No tables found in public schema after restore")
                all_ok = False
    except Exception as e:
        _status("Table count query", "FAIL", str(e))
        all_ok = False

    # ── Cleanup ──────────────────────────────────────────────────────
    print("\nCleanup:")
    _cleanup(temp_container)

    # ── Final verdict ────────────────────────────────────────────────
    print(f"\n{'='*60}")
    if all_ok:
        print("  DRILL PASSED — backup and restore verified successfully.")
        print(f"{'='*60}\n")
        sys.exit(0)
    else:
        print("  DRILL FAILED — one or more steps did not pass.")
        print(f"{'='*60}\n")
        sys.exit(1)


def _cleanup(container: str):
    """Stop and remove the temporary container."""
    try:
        _run(["docker", "rm", "-f", container], check=False, timeout=15)
        _status(f"Remove {container}", "PASS")
    except Exception as e:
        _status(f"Remove {container}", "FAIL", str(e))


def _fail_exit():
    print(f"\n{'='*60}")
    print("  DRILL FAILED — one or more steps did not pass.")
    print(f"{'='*60}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
