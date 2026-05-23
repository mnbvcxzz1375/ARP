# Phase 4 Design: User Dashboard API

**Date**: 2026-05-19
**Status**: Approved
**Scope**: AgentNet Enterprise Dashboard — Phase 4 of 13
**Predecessor**: Phase 3 (RBAC Permission Helpers)

## Summary

Build all user-facing Dashboard API endpoints under `/v1/dashboard/*`. These are API-layer aggregations that serve the user console pages. Each endpoint uses RBAC dependencies from Phase 3 and session auth from Phase 2. No admin endpoints yet — those are Phase 5.

## Endpoints

All endpoints require authenticated session (via `CurrentSession` dependency from Phase 2).

### GET /v1/dashboard/overview

User's personal overview KPIs and recent activity.

Response:
```json
{
  "online_agents": 3,
  "tasks_today": 42,
  "failed_tasks": 2,
  "pending_approvals": 1,
  "pending_messages": 0,
  "recent_tasks": [...],
  "recent_approvals": [...],
  "recent_agent_status_changes": [...]
}
```

- `online_agents`: count of user's agents with active WebSocket presence (Redis).
- `tasks_today`: tasks created today by user.
- `failed_tasks`: tasks with status=failed in last 24h.
- `pending_approvals`: approvals with status=pending for user's agents.
- `pending_messages`: undelivered messages for user's agents.
- `recent_tasks`: last 10 tasks (id, status, target, created_at).
- `recent_approvals`: last 10 approvals (id, status, risk_level, created_at).
- `recent_agent_status_changes`: last 10 agent status changes from audit log.

**Permission**: `agent:read:own` (all roles have this).
**Caching**: Redis snapshot cache, TTL 15s (from config).

### GET /v1/dashboard/agents

User's agent list.

Query params: `offset=0`, `limit=50`, `status=`, `runtime=`, `inbound_policy=`, `search=`

Response:
```json
{
  "agents": [{
    "agent_id": "...",
    "agent_number": "...",
    "name": "...",
    "runtime": "...",
    "status": "online|offline",
    "inbound_policy": "...",
    "discoverable": false,
    "capabilities": ["..."],
    "created_at": "...",
    "updated_at": "...",
    "last_seen_at": "..."
  }],
  "total": 42,
  "offset": 0,
  "limit": 50
}
```

- `status`: derived from Redis presence (online/offline).
- `last_seen_at`: from audit log or agent model.

**Permission**: `agent:read:own`.

### POST /v1/dashboard/agents

Create a new agent for the current user.

Request body:
```json
{"name": "my-agent", "runtime": "python", "inbound_policy": "public", "discoverable": false, "capabilities": ["code-review"]}
```

**Permission**: `agent:create`.

### GET /v1/dashboard/agents/{agent_id}

Agent detail page.

Response includes metadata, token metadata (not the token itself), recent tasks, recent connection requests, recent audit timeline.

**Permission**: `agent:read:own` + check agent belongs to current user.

### PATCH /v1/dashboard/agents/{agent_id}

Edit agent metadata (name, inbound_policy, discoverable, capabilities).

Request body: subset of agent fields.

**Permission**: `agent:edit:own` + ownership check.

### DELETE /v1/dashboard/agents/{agent_id}

Delete agent.

**Permission**: `agent:delete:own` + ownership check.

### POST /v1/dashboard/agents/{agent_id}/rotate-token

Rotate agent token.

**Permission**: `agent:rotate-token:own` + ownership check.

### GET /v1/dashboard/tasks

Task list.

Query params: `offset=0`, `limit=50`, `status=`, `sender=`, `target=`, `date_from=`, `date_to=`, `error_code=`

Response:
```json
{
  "tasks": [{
    "task_id": "...",
    "status": "...",
    "sender_agent": "...",
    "target_agent": "...",
    "created_at": "...",
    "updated_at": "...",
    "duration_sec": 5,
    "error_code": null,
    "risk_level": null,
    "delivery_status": "..."
  }],
  "total": 42,
  "offset": 0,
  "limit": 50
}
```

**Permission**: `task:read:own`.

### GET /v1/dashboard/tasks/{task_id}

Task detail.

Response: metadata, payload preview (masked if contains secrets), result preview, error_message, message timeline, progress timeline, approval timeline, audit timeline, delivery_status, retry_count, lease_status.

**Permission**: `task:read:detail:own` + ownership check (task.created_by or task.assigned_to belongs to user).

### GET /v1/dashboard/tasks/{task_id}/messages

Task messages.

**Permission**: same as task detail.

### GET /v1/dashboard/tasks/{task_id}/progress

Task progress entries.

**Permission**: same as task detail.

### GET /v1/dashboard/approvals

Approval center. Two types:
1. Task Action Approvals — high-risk adapter operations
2. Connection Approvals — cross-agent connection requests

Query params: `offset=0`, `limit=50`, `type=task|connection`, `status=`, `risk_level=`

**Permission**: `approval:handle:own`.

### POST /v1/dashboard/approvals/{approval_id}/accept

Accept approval.

**Permission**: `approval:handle:own` + ownership check.

### POST /v1/dashboard/approvals/{approval_id}/reject

Reject approval.

**Permission**: `approval:handle:own` + ownership check.

### GET /v1/dashboard/connections

Connection requests / Agent Firewall.

Response:
```json
{
  "agents": [{
    "agent_id": "...",
    "agent_number": "...",
    "inbound_policy": "...",
    "pending_requests": 2,
    "accepted_connections": 5,
    "rejected_connections": 1,
    "last_decision_at": "..."
  }],
  "pending_requests": [{
    "connection_id": "...",
    "agent_number": "...",
    "requester_agent": "...",
    "requested_policy": "...",
    "created_at": "..."
  }]
}
```

**Permission**: `connection:manage:own` + `firewall:manage:own`.

### POST /v1/dashboard/connections/{connection_id}/accept

Accept connection request.

**Permission**: `connection:manage:own`.

### POST /v1/dashboard/connections/{connection_id}/reject

Reject connection request.

**Permission**: `connection:manage:own`.

### PATCH /v1/dashboard/agents/{agent_id}/firewall

Update agent inbound policy and allowed/denied contacts.

Request body:
```json
{
  "inbound_policy": "contacts_only",
  "allowed_contacts": ["AN-GLOBAL-XXXX"],
  "denied_contacts": ["AN-GLOBAL-YYYY"]
}
```

**Permission**: `firewall:manage:own`.

### GET /v1/dashboard/api-keys

List API keys.

Response: key_id, name, key_prefix, created_at, expires_at, revoked_at.

**Permission**: `apikey:manage:own`.

### POST /v1/dashboard/api-keys

Create API key.

Request: `{"name": "deploy-key", "expires_at": "2026-12-31T23:59:59Z"}`

Response: includes the plain API key (one-time).

**Permission**: `apikey:manage:own`.

### POST /v1/dashboard/api-keys/{api_key_id}/revoke

Revoke API key.

Request: `{"allow_last_key": false}` (default: refuse to revoke last active key).

**Permission**: `apikey:manage:own`.

## File Structure

| File | Operation | Responsibility |
|------|-----------|---------------|
| `apps/api/app/routers/dashboard_user.py` | Create | All user dashboard endpoints |
| `apps/api/app/schemas/dashboard.py` | Create | Pydantic request/response schemas for dashboard |
| `apps/api/app/services/dashboard_service.py` | Create | Aggregation logic (overview KPIs, online status) |
| `apps/api/app/main.py` | Modify | Register dashboard_user router |
| `apps/api/tests/test_phase_web_4_user_api.py` | Create | Endpoint tests |
| `reports/web_phase_4_report.md` | Create | Phase report |

## Ownership Enforcement

All "own" permissions require the resource to belong to the current user:
- Agents: `agent.owner_id == user.id`
- Tasks: `task.created_by == user's agent` OR `task.assigned_to == user's agent`
- Approvals: approval's agent belongs to user
- API keys: `api_key.user_id == user.id`

This is enforced at the service layer, not just the permission layer. `has_permission` checks role, but the service checks ownership.

## Secret Masking

- Task payloads/results: scan for patterns matching `sk-...`, `agt_sk_...`, `ak_...` and replace with `***`.
- Agent token: never returned. Only metadata (prefix, created_at, rotated_at).
- API keys: only `key_prefix` returned, never the full key except on creation.

## Assumptions

- Phase 1: all models exist (User, Agent, Task, Message, Approval, Connection, ApiKey, AuditLog).
- Phase 2: session auth and CSRF infrastructure exist.
- Phase 3: RBAC permission helpers exist.
- Redis presence: agent online status available via `ws:presence:{agent_id}` key (from Phase 2 connection manager).
- No frontend pages in this phase — API only.
