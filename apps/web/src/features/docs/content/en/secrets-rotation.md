# Secret Management and Rotation

This document defines the secret classification, storage locations, rotation
intervals, rotation steps, and audit requirements for a single-node AgentNet
Docker Compose deployment.

## Purpose

Limit the impact of a leaked API key, agent token, database password, Redis
password, Grafana password, TLS private key, or CI secret, and keep the
rotation process auditable, verifiable, and rollback-capable.

## Secret classification

| Type | Example | Purpose | Plaintext policy |
| --- | --- | --- | --- |
| User API key | `ak_...` | REST API authentication | shown once at creation |
| Agent token | `agt_sk_...` | WebSocket agent authentication | shown once at creation or rotation |
| Postgres password | `POSTGRES_PASSWORD` | Database authentication | only in `.env.production` and the operator secret store |
| Redis password | `REDIS_PASSWORD` | Redis authentication | only in `.env.production` |
| Grafana admin password | `GRAFANA_ADMIN_PASSWORD` | Initial Grafana admin | only in `.env.production` |
| TLS private key | `privkey.pem` | HTTPS termination | readable only by server root/operator |
| CI secrets | GitHub Secrets | CI/CD release and external integrations | never written to logs |
| External service tokens | future extension | Adapter or integration calls | managed per the service policy |

## Storage strategy

- The Docker Compose VPS setup uses `infra/.env.production` by default.
- `infra/.env.production` must be ignored by `.gitignore`.
- Recommended Linux permissions:

```bash
chmod 600 infra/.env.production
chown deploy:deploy infra/.env.production
```

- GitHub Actions uses GitHub Secrets; secrets never go into workflow files.
- The local CLI configuration may hold an API key; developer machines should
  use disk encryption and account protection.
- No cloud Secret Manager is introduced in this cycle; add one when migrating
  to a cloud platform.

## Suggested rotation intervals

| Secret | Interval | Triggers |
| --- | --- | --- |
| User API key | 90 days | personnel change, lost machine, suspected leak |
| Agent token | 90 days | machine migration, agent image leak, suspected leak |
| Postgres password | 180 days | operator change, backup leak, suspected leak |
| Redis password | 180 days | operated in sync with the Postgres password |
| Grafana admin password | 180 days | admin change, suspected leak |
| TLS private key | certificate cycle | private key leak, certificate renewal |
| CI secrets | 90 days or vendor guidance | runner log leak, permission change |

## API key rotation

The current release supports creating, listing, and revoking API keys over
REST and CLI. Production rotation follows these principles:

1. Create a new API key for the user.
2. Update all caller configurations.
3. Verify with the new key against `/v1/agents`.
4. Revoke the old key.
5. Verify the old key now returns 401.

Verification commands:

```powershell
agentnet key create --name rotated-2026-05
agentnet key list
agentnet key revoke <old_api_key_id>
curl.exe -s "$env:PUBLIC_BASE_URL/v1/agents" -H "Authorization: Bearer ak_NEW"
curl.exe -i "$env:PUBLIC_BASE_URL/v1/agents" -H "Authorization: Bearer ak_OLD"
```

Audit points:

- The operator who created the new key.
- The key prefix.
- The revoke time.
- Affected systems.

## Agent token rotation

1. Call the rotate token API:

```powershell
curl.exe -s -X POST "$env:PUBLIC_BASE_URL/v1/agents/$env:AGENT_ID/rotate-token" `
  -H "Authorization: Bearer $env:API_KEY"
```

2. Save the new `agt_sk_...` from the response; the old token is invalid
   immediately.
3. Update the agent runtime environment variable `AGENTNET_AGENT_TOKEN`.
4. Restart the agent.
5. Verify the WebSocket connection succeeds.
6. Connect with the old token and confirm it returns `INVALID_TOKEN`.

Audit points:

- Agent ID / agent number.
- Who initiated the rotation.
- Rotation time.
- Agent restart time.
- The failed verification result for the old token.

## Postgres password rotation

1. Enter a maintenance window.
2. Take a database backup:

```powershell
./scripts/backup/postgres_backup.ps1
```

3. Stop the API:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production stop api
```

4. Change the password inside Postgres.
5. Update `POSTGRES_PASSWORD` and `DATABASE_URL` in `infra/.env.production`.
6. Start the API:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up -d api
```

7. Verify:

```powershell
curl.exe http://localhost/healthz
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic current
```

Rollback:

- If the API cannot connect to the database, restore the old password and the
  old `.env.production`, then restart the API.
- If the database state is abnormal, follow `docs/backup-restore.md` for
  recovery.

## Redis password rotation

Redis data is not a long-term source of truth. Rotation may briefly lose the
pending queue, presence, and rate limit state:

1. Enter a maintenance window.
2. Stop the API and Redis.
3. Update `REDIS_PASSWORD` and `REDIS_URL`.
4. Recreate the Redis container.
5. Start the API.
6. Check `/healthz` and the WebSocket connections.

## Leak response

When a secret leaks, follow `docs/incident-secret-leak.md`. Minimum actions:

- Revoke or rotate immediately.
- Review the audit logs.
- Check for anomalous tasks, approvals, and connections.
- Check the CI logs for exposure.
- Produce an incident note.

## Common failure causes

- The new key was not propagated to all callers, so some services get 401.
- Revoking the last active API key is refused by default; locking the account
  out requires explicitly passing `allow_last_key=true` or the CLI flag
  `--allow-last-key`.
- The agent was not restarted after the token rotation.
- `POSTGRES_PASSWORD` was updated in `.env.production` but `DATABASE_URL` was
  forgotten.
- No maintenance window during rotation, so task delivery was interrupted.

## Security notes

- Never paste full tokens into Slack, issues, READMEs, reports, or
  screenshots.
- A plaintext token is shown only once, at creation or rotation.
- Shell history may retain secrets; control shell history on production
  machines.
