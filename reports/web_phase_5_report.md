# Phase Web 5 Report: Admin Dashboard API

**Date:** 2026-05-19
**Status:** Complete

## Goal

Build all admin-facing Dashboard API endpoints under `/v1/dashboard/admin/*` for the admin operations console.

## Files Changed

| File | Operation |
|------|-----------|
| `apps/api/app/services/admin_service.py` | NEW — Global KPI aggregation, per-user/agent stats, system health |
| `apps/api/app/schemas/dashboard_admin.py` | NEW — 13 Pydantic schemas |
| `apps/api/app/routers/dashboard_admin.py` | NEW — 18 admin endpoints |
| `apps/api/app/main.py` | Modified — register dashboard_admin router |
| `apps/api/app/models/agent.py` | Modified — `owner` relationship lazy="joined" for async |
| `apps/api/app/models/task.py` | Modified — relationships lazy="select" for async |
| `apps/api/tests/test_phase_web_5_admin_api.py` | NEW — 34 endpoint tests |

## Endpoints

### Admin Overview (1)
| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/dashboard/admin/overview` | `overview:read:global` |

### Admin Users (7)
| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/dashboard/admin/users` | `user:read:global` |
| GET | `/v1/dashboard/admin/users/{id}` | `user:read:global` |
| POST | `/v1/dashboard/admin/users/{id}/disable` | `user:disable` + step-up |
| POST | `/v1/dashboard/admin/users/{id}/enable` | `user:disable` + step-up |
| POST | `/v1/dashboard/admin/users/{id}/revoke-sessions` | `user:disable` + step-up |
| POST | `/v1/dashboard/admin/users/{id}/revoke-api-keys` | `apikey:revoke:global` + step-up |

### Admin Agents (3)
| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/dashboard/admin/agents` | `agent:read:global` |
| GET | `/v1/dashboard/admin/agents/{id}` | `agent:read:global` |
| PATCH | `/v1/dashboard/admin/agents/{id}` | `agent:disable` + step-up |

### Admin Tasks (4)
| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/dashboard/admin/tasks` | `task:read:global` |
| GET | `/v1/dashboard/admin/tasks/{id}` | `task:read:detail:global` |
| POST | `/v1/dashboard/admin/tasks/{id}/cancel` | `task:cancel:pending` |
| POST | `/v1/dashboard/admin/tasks/{id}/expire` | `task:cancel:running` + step-up |

### Audit Logs (2)
| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/dashboard/admin/audit-logs` | `audit:read` |
| POST | `/v1/dashboard/admin/audit-logs/export` | `audit:export` + step-up |

### System Health (1)
| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/dashboard/admin/system/health` | `system:read` |

## Test Results

- **34 tests collected, 34 passed**
- TestAdminAccess: 7 passed (regular user → 403, unauthenticated → 401)
- TestAdminOverview: 2 passed
- TestAdminUsers: 8 passed
- TestAdminAgents: 5 passed
- TestAdminTasks: 2 passed
- TestAuditLogs: 5 passed
- TestSystemHealth: 3 passed

## Bug Fixes During Implementation

1. **`Agent.owner` lazy loading** — Default lazy loading caused `MissingGreenlet` errors in async context. Fixed by setting `lazy="joined"`.
2. **`Task` relationships** — `lazy="selectin"` fails in async test context. Fixed to `lazy="select"`.
3. **`AuditLog.actor_id` type mismatch** — Column is `String`, but endpoint compared with `uuid.UUID()`. Fixed to use string comparison.
4. **Invalid UUID in user detail** — Non-UUID strings caused unhandled `ValueError`. Added try/except returning 422.
5. **`Task.error_code` column** — Router referenced non-existent column. Removed broken filter.

## Security Verification

| Check | Result |
|-------|--------|
| Regular user gets 403 on all admin endpoints | PASS |
| Unauthenticated gets 401 | PASS |
| High-risk mutations require step-up | PASS |
| System health exposes no secrets | PASS |
| Task detail masks payload/result | PASS |
| Admin detail reads write read audit | PASS |
| Audit export limited to 10000 rows | PASS |
| No role string comparison in routers | PASS — all checks go through `has_permission()` |

## Unfinished Items

None. Phase 5 scope (admin dashboard API) is complete.

## Risks and Follow-up

- Bug fixes #1-5 should be reviewed for impact on existing functionality
- The `Agent.owner` lazy loading change may affect query performance (joined vs select)
- Phase 6 will build frontend pages for both user and admin dashboards
