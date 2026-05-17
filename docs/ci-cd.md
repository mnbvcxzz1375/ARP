# CI/CD

This document describes the AgentNet CI/CD quality gates added in Phase 11.1.

## Purpose

The CI pipeline proves that the monorepo can be installed, migrated, tested, compiled, and checked from a clean environment. It is intentionally conservative: a failing database migration, protocol contract drift, or broken Docker Compose file should stop the pipeline.

## Workflows

### CI

File:

```text
.github/workflows/ci.yml
```

Triggers:

- Push to `main`
- Push to `codex/**`
- Pull requests

Checks:

- Install API, SDK, CLI, base adapter, and OpenClaw adapter as editable packages.
- Start PostgreSQL and Redis service containers.
- Run Alembic `upgrade head`.
- Run all tests from the repository root.
- Confirm protocol contract tests are collected by pytest.
- Run `compileall` over production Python packages.
- Validate local Docker Compose configuration.

### Release Check

File:

```text
.github/workflows/release-check.yml
```

Trigger:

- Manual `workflow_dispatch`

The release check runs the current quality gates and creates a release readiness artifact. In Phase 11.1 it also audits later Phase 11 artifacts, such as production compose, OpenAPI export, backup scripts, and observability config.

The workflow input `strict_phase11` controls whether missing later-phase artifacts fail the job:

- `false`: report missing artifacts without failing. This is the default while Phase 11 is still in progress.
- `true`: fail if any later Phase 11 artifact is missing. Use this after Phase 11.8.

## Local Commands

PowerShell:

```powershell
./scripts/ci/install.ps1
./scripts/ci/check-alembic.ps1
./scripts/ci/run-tests.ps1
./scripts/ci/check-compile.ps1
./scripts/ci/check-compose.ps1
```

Bash:

```bash
bash scripts/ci/install.sh
bash scripts/ci/check-alembic.sh
bash scripts/ci/run-tests.sh
bash scripts/ci/check-compile.sh
bash scripts/ci/check-compose.sh
```

## Environment

CI uses these service defaults:

```text
DATABASE_URL=postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet
REDIS_URL=redis://localhost:6379/0
DB_POOL_PRE_PING=true
DB_NULL_POOL=true
RATE_LIMIT_IP_MAX=999999
RATE_LIMIT_USER_MAX=999999
RATE_LIMIT_AGENT_MAX=999999
RATE_LIMIT_GLOBAL_MAX=999999
```

The high rate limit values avoid accidental throttling during tests. They are test-only values and must not be copied into production.

## Failure Guide

### Install Fails

Check the package metadata in:

```text
apps/api/pyproject.toml
packages/python-sdk/pyproject.toml
packages/cli/pyproject.toml
adapters/base/pyproject.toml
adapters/openclaw/pyproject.toml
```

### Alembic Fails

Run locally:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet"
./scripts/ci/check-alembic.ps1
```

Common causes:

- PostgreSQL is not running.
- A migration and SQLAlchemy model disagree.
- A migration assumes a constraint name that does not exist.

### Tests Fail

Run:

```powershell
python -m pytest -q
```

Then narrow to the failing module:

```powershell
python -m pytest apps/api -q
python -m pytest packages/python-sdk -q
python -m pytest packages/cli -q
python -m pytest adapters/openclaw -q
```

### Protocol Contract Collection Fails

The command:

```powershell
python -m pytest apps/api/tests/test_protocol_contract.py --collect-only -q
```

must list the contract tests. Test classes must start with `Test`, otherwise pytest will not collect them.

### Docker Compose Check Fails

Run:

```powershell
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config
```

Common causes:

- Docker Desktop is not running locally.
- Compose file paths changed.
- A volume path references a missing directory.

## Security Notes

- CI must not print API keys, Agent tokens, database passwords, or private keys.
- GitHub Actions secrets should be used only when later deployment workflows need real credentials.
- Current CI uses local service container credentials that are not production secrets.

