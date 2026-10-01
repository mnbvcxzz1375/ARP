# Secret Leak Incident Response

This document defines the response process after discovering a leaked API
key, agent token, database password, Redis password, Grafana password, TLS
private key, or CI secret.

## Purpose

Cut off the leaked secret's access as fast as possible, determine the blast
radius, restore service, and leave a traceable record.

## Incident grading

| Level | Example | Response |
| --- | --- | --- |
| P0 | Database password, TLS private key, CI deploy token leaked | Immediate maintenance window, rotate, audit access |
| P1 | User API key or agent token leaked | Revoke/rotate immediately, check for anomalous operations |
| P2 | Grafana admin password leaked | Rotate the password, check dashboards and datasources |

## Immediate actions

1. Record the discovery time, who found it, and where the leak is.
2. Do not copy the full secret into more channels.
3. Truncate the evidence; keep only a prefix, a hash, or a redacted
   screenshot.
4. Confirm the secret type.
5. Revoke or rotate by type.

## API key leak

1. Create a replacement key.
2. Update the callers.
3. Revoke the old key.
4. Query the audit logs for:
   - anomalous task creation.
   - anomalous agent creation or deletion.
   - anomalous connection or approval operations.
5. Verify the old key now returns 401.

## Agent token leak

1. Call the agent token rotation API.
2. Update the agent environment variables.
3. Restart the agent.
4. Verify the old token's WebSocket connection now returns
   `INVALID_TOKEN`.
5. Review the agent's recent tasks, messages, approvals, and connections.

## Database password leak

1. Enter a maintenance window immediately.
2. Take a backup.
3. Rotate the database password.
4. Update `.env.production`.
5. Restart the API.
6. Inspect database connection sources and anomalous queries.
7. If data tampering is suspected, follow the backup restore process for
   forensics and recovery.

## CI secret leak

1. Delete or replace the secret in GitHub Secrets.
2. Cancel any suspicious running workflows.
3. Check whether Actions logs contain plaintext.
4. Rotate tokens for downstream systems.
5. Verify that recent release artifacts are still trustworthy.

## Incident note template

```markdown
# Secret Leak Incident

## Summary

## Timeline

## Secret Type

## Exposure Source

## Immediate Containment

## Rotation / Revocation Steps

## Audit Findings

## User Impact

## Follow-up Actions
```

## Verification commands

```powershell
curl.exe -i "$env:PUBLIC_BASE_URL/v1/agents" -H "Authorization: Bearer ak_OLD"
curl.exe -s "$env:PUBLIC_BASE_URL/healthz"
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs --tail 200 api
```

## Security notes

- Incident records must never contain the full secret.
- External communication should only state the impact scope and the handling
  status.
- If the leak came from a git commit, rotating the secret is not enough: clean
  the history or restrict repository access, since deleting the file does not
  remove the exposure.
