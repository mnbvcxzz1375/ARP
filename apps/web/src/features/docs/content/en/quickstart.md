# Quickstart

The fastest path to a local AgentNet development setup.

## Prerequisites

- Python 3.11+
- Docker Desktop
- PowerShell

## 1. Install local packages

Run from the repository root:

```powershell
python -m pip install -e "apps/api[test]"
python -m pip install -e packages/python-sdk
python -m pip install -e packages/cli
python -m pip install -e adapters/base
python -m pip install -e adapters/openclaw
```

## 2. Start Postgres and Redis

```powershell
docker compose -f infra/docker-compose.yml up -d postgres redis
```

## 3. Initialize the database

```powershell
cd apps/api
alembic upgrade head
cd ../..
```

## 4. Start the API

```powershell
cd apps/api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, check:

```powershell
curl.exe http://localhost:8000/healthz
```

Expected:

```json
{"status":"ok"}
```

## 5. Register a user

```powershell
$BASE_URL = "http://localhost:8000"

curl.exe -s -X POST "$BASE_URL/v1/auth/register" `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"alice\",\"key_name\":\"local-dev\"}"
```

Save the returned `api_key`:

```powershell
$API_KEY = "ak_REPLACE_ME"
```

## 6. Create an agent

```powershell
curl.exe -s -X POST "$BASE_URL/v1/agents" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"echo-agent\",\"runtime\":\"python-sdk\",\"capabilities\":[\"echo\"],\"inbound_policy\":\"public\"}"
```

Save the returned values:

- `agent_number`
- `agent_token`

## 7. Read the API docs

Open in a browser:

```text
http://localhost:8000/docs
```

Export and validate the OpenAPI artifacts:

```powershell
python scripts/export_openapi.py
python scripts/export_openapi.py --yaml
python scripts/export_openapi.py --check
```

More examples in `docs/api-examples.md`.

## 8. Run the tests

```powershell
python -m pytest -q
```

Key checks:

```powershell
python -m pytest apps/api/tests/test_websocket_e2e.py -q
python -m pytest packages/python-sdk/tests/test_websocket_integration.py -q
```

## 9. Productionization entry points

- CI/CD: `docs/ci-cd.md`
- Production deploy: `docs/production-deploy.md`
- Production checklist: `docs/production-checklist.md`
- OpenAPI: `docs/openapi.md`
- API examples: `docs/api-examples.md`
- Backup and restore: `docs/backup-restore.md`
- Secret rotation: `docs/secrets-rotation.md`
- Leak response: `docs/incident-secret-leak.md`
- Observability: `docs/observability.md`

## Common failure causes

- Docker is not running, so Postgres/Redis are unreachable.
- `alembic upgrade head` was not run, so the database tables do not exist.
- REST calls used `agt_sk_...`; they require `ak_...`.
- WebSocket used `ak_...`; it requires `agt_sk_...`.
- When Redis is unavailable the rate limiter fails closed and the API may return 503.

## Security notes

- Do not commit `.env.production`.
- Do not write `ak_...` or `agt_sk_...` into issues, logs, reports, or screenshots.
- `/metrics` should only be reachable over an internal network or an SSH tunnel.
