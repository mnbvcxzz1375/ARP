# Phase 5 Design: Admin Dashboard API

**Date**: 2026-05-19
**Status**: Approved
**Scope**: AgentNet Enterprise Dashboard — Phase 5 of 13
**Predecessor**: Phase 4 (User Dashboard API)

## Summary

Build all admin-facing Dashboard API endpoints under `/v1/dashboard/admin/*`. These serve the admin operations console. All endpoints require `admin` or `super_admin` role via Phase 3 RBAC. High-risk mutations require `super_admin + step-up`.

## Endpoints

### GET /v1/dashboard/admin/overview

Global KPIs. Permission: `overview:read:global`.

Response:
```json
{
  "total_users": 42,
  "active_users": 38,
  "disabled_users": 4,
  "total_agents": 120,
  "online_agents": 15,
  "active_ws_connections": 23,
  "tasks_1h": 150,
  "tasks_24h": 2400,
  "tasks_7d": 12000,
  "failed_tasks": 12,
  "expired_tasks": 5,
  "pending_approvals": 3,
  "pending_messages": 8,
  "retry_worker_health": "ok",
  "timeout_worker_health": "ok",
  "api_5xx_rate": 0.02
}
```

Worker health: derived from checking if worker tasks are still running (via app lifespan tracking or Redis heartbeat). For MVP, report "ok" if API is up.

### GET /v1/dashboard/admin/users

User list. Permission: `user:read:global`.

Query: `offset`, `limit`, `role`, `disabled`, `date_from`, `date_to`, `search`

Response includes per-user aggregates: agents_count, active_api_keys_count, tasks_24h, failed_tasks_24h.

### GET /v1/dashboard/admin/users/{user_id}

User detail. Permission: `user:read:global`. Writes read audit log.

Response: metadata, agents list (summary), api key list (metadata only), tasks summary, approvals summary, recent audit, sessions summary.

### POST /v1/dashboard/admin/users/{user_id}/disable

Disable/Enable user. Body: `{is_disabled: true|false}`. Permission: `user:disable` (super_admin only) + require_high_risk.

### POST /v1/dashboard/admin/users/{user_id}/force-revoke-keys

Revoke all API keys and active dashboard sessions. Permission: `apikey:revoke:global` (super_admin only) + require_high_risk.

### GET /v1/dashboard/admin/agents

Global agent list. Permission: `agent:read:global`.

Query: `offset`, `limit`, `status`, `runtime`, `owner_id`, `search`

Response includes per-agent: owner username, tasks_24h, failed_tasks_24h.

### GET /v1/dashboard/admin/agents/{agent_id}

Agent detail. Permission: `agent:read:global`. Writes read audit.

Response: metadata, owner, token metadata, connection policy, recent tasks, recent audit, connection history, error summary.

### GET /v1/dashboard/admin/tasks

Global task list. Permission: `task:read:global`.

Query: `offset`, `limit`, `user_id`, `agent_id`, `status`, `date_from`, `date_to`, `error_code`, `risk_level`

### GET /v1/dashboard/admin/tasks/{task_id}

Task detail. Permission: `task:read:detail:global`. Writes read audit. Masks payload.

### POST /v1/dashboard/admin/tasks/{task_id}/cancel

Cancel task. admin: only pending/delivered tasks. super_admin: any task including running.

Permission: `task:cancel:pending` (admin) or `task:cancel:running` (super_admin + step-up).

### POST /v1/dashboard/admin/tasks/{task_id}/expire

Force expire task. Permission: `task:cancel:running` + require_high_risk.

### GET /v1/dashboard/admin/audit-logs

Audit log query. Permission: `audit:read`.

Query: `offset`, `limit`, `actor_type`, `actor_id`, `action`, `resource_type`, `resource_id`, `task_id`, `created_from`, `created_to`

### GET /v1/dashboard/admin/audit-logs/export

Async audit export. Permission: `audit:export` + require_high_risk.

Returns a download URL or job ID. For MVP, return CSV content directly (limited to 10000 rows).

### GET /v1/dashboard/admin/system-health

System health summary. Permission: `system:read`.

Response: API health, DB health, Redis health, migration revision, app version, worker status, pending queue length, retry backlog, HTTPS/WSS staging gate.

NO secrets: no DATABASE_URL, REDIS_URL, API keys, passwords, connection strings.

## File Structure

| File | Operation | Responsibility |
|------|-----------|---------------|
| `apps/api/app/services/admin_service.py` | Create | Admin aggregation (overview KPIs, user/agent/task stats) |
| `apps/api/app/routers/dashboard_admin.py` | Create | All admin endpoints |
| `apps/api/app/schemas/dashboard_admin.py` | Create | Admin-specific schemas |
| `apps/api/app/main.py` | Modify | Register dashboard_admin router |
| `apps/api/tests/test_phase_web_5_admin_api.py` | Create | Admin endpoint tests |
| `reports/web_phase_5_report.md` | Create | Phase report |

## Security Requirements

- All `/v1/dashboard/admin/*` endpoints require authenticated session with `admin` or `super_admin` role.
- High-risk mutations (disable user, revoke keys, cancel running task, export audit) require `super_admin` + step-up.
- Admin detail reads (user detail, agent detail, task detail) write read audit log.
- System health NEVER exposes secrets (DATABASE_URL, REDIS_URL, tokens, passwords).
- Payload masking on task detail (same as user dashboard).
- Audit export limited to 10000 rows in MVP.

## Assumptions

- Phase 1: all models exist (User, Agent, Task, Message, Approval, AuditLog, DashboardSession).
- Phase 2: session auth, CSRF, step-up infrastructure.
- Phase 3: RBAC permission helpers (`require_permission`, `require_high_risk`).
- Phase 4: user dashboard infrastructure exists.
- Worker health: for MVP, report "ok" if API process is alive.
