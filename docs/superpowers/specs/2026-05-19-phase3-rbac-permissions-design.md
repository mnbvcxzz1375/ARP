# Phase 3 Design: RBAC Permission Helpers + Endpoint Guards

**Date**: 2026-05-19
**Status**: Approved
**Scope**: AgentNet Enterprise Dashboard — Phase 3 of 13
**Predecessor**: Phase 2 (Session/Auth/CSRF)

## Summary

Build the backend RBAC layer: a permission helper module that maps roles to permissions, and FastAPI dependencies that protect endpoints. No endpoint code changes yet — just the infrastructure. All permission checks go through a single helper; role strings are never compared directly in routers.

## Core Principle

> `user | admin | super_admin` 只是角色名。真实判断必须走 permission helper，不能在页面或 router 中散写字符串判断。
> 后端必须作为最终权限边界；前端隐藏按钮只能作为体验优化，不能作为安全控制。

## Permission Model

### Roles

```text
user        — owns resources, can manage own agents/tasks/approvals/keys
admin       — can read global resources, cancel pending tasks, low-risk ops
super_admin — all permissions including disable user/agent, revoke keys, export audit
```

### Permission Constants

Each permission is a string constant, grouped by resource area:

```python
# User/Agent ownership (all roles)
PERM_READ_OWN_AGENTS = "agent:read:own"
PERM_CREATE_AGENT = "agent:create"
PERM_EDIT_OWN_AGENT = "agent:edit:own"
PERM_DELETE_OWN_AGENT = "agent:delete:own"
PERM_ROTATE_OWN_TOKEN = "agent:rotate-token:own"

# Task ownership (all roles)
PERM_READ_OWN_TASKS = "task:read:own"
PERM_CREATE_TASK = "task:create"
PERM_READ_OWN_TASK_DETAIL = "task:read:detail:own"
PERM_HANDLE_OWN_APPROVAL = "approval:handle:own"

# Connection/Firewall (all roles)
PERM_MANAGE_OWN_CONNECTIONS = "connection:manage:own"
PERM_MANAGE_OWN_FIREWALL = "firewall:manage:own"

# API keys (all roles)
PERM_MANAGE_OWN_KEYS = "apikey:manage:own"

# Global read (admin+)
PERM_READ_GLOBAL_OVERVIEW = "overview:read:global"
PERM_READ_GLOBAL_USERS = "user:read:global"
PERM_READ_GLOBAL_AGENTS = "agent:read:global"
PERM_READ_GLOBAL_TASKS = "task:read:global"
PERM_READ_GLOBAL_TASK_DETAIL = "task:read:detail:global"
PERM_READ_AUDIT_LOGS = "audit:read"

# Admin low-risk mutations
PERM_CANCEL_PENDING_TASK = "task:cancel:pending"

# Super-admin only
PERM_EXPORT_AUDIT = "audit:export"
PERM_DISABLE_USER = "user:disable"
PERM_DISABLE_AGENT = "agent:disable"
PERM_CANCEL_RUNNING_TASK = "task:cancel:running"
PERM_FORCE_REVOKE_KEYS = "apikey:revoke:global"
PERM_MODIFY_SECURITY_POLICY = "security:modify"
PERM_READ_SYSTEM = "system:read"
```

### Role-to-Permission Mapping

```python
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "user": {
        PERM_READ_OWN_AGENTS, PERM_CREATE_AGENT, PERM_EDIT_OWN_AGENT,
        PERM_DELETE_OWN_AGENT, PERM_ROTATE_OWN_TOKEN,
        PERM_READ_OWN_TASKS, PERM_CREATE_TASK, PERM_READ_OWN_TASK_DETAIL,
        PERM_HANDLE_OWN_APPROVAL,
        PERM_MANAGE_OWN_CONNECTIONS, PERM_MANAGE_OWN_FIREWALL,
        PERM_MANAGE_OWN_KEYS,
    },
    "admin": ROLE_PERMISSIONS["user"] | {
        PERM_READ_GLOBAL_OVERVIEW, PERM_READ_GLOBAL_USERS,
        PERM_READ_GLOBAL_AGENTS, PERM_READ_GLOBAL_TASKS,
        PERM_READ_GLOBAL_TASK_DETAIL, PERM_READ_AUDIT_LOGS,
        PERM_CANCEL_PENDING_TASK,
    },
    "super_admin": ROLE_PERMISSIONS["admin"] | {
        PERM_EXPORT_AUDIT, PERM_DISABLE_USER, PERM_DISABLE_AGENT,
        PERM_CANCEL_RUNNING_TASK, PERM_FORCE_REVOKE_KEYS,
        PERM_MODIFY_SECURITY_POLICY, PERM_READ_SYSTEM,
    },
}
```

### High-Risk vs Low-Risk Operations

High-risk operations (require super_admin + step-up):
- Disable/enable user, disable/enable agent, force revoke API keys
- Cancel running task, force expire task
- Export audit logs, modify system security policy
- Any batch operation

Low-risk operations (admin can do without step-up):
- Read global metadata, lists, summaries
- Cancel pending (not yet accepted) tasks
- Acknowledge alerts, add operator notes
- Read sanitized system health

## API Design

### `app/services/rbac_service.py`

```python
def has_permission(user: User, permission: str) -> bool:
    """Check if user has the given permission. Returns False for disabled users."""

def require_permission(permission: str):
    """FastAPI dependency: raises 403 FORBIDDEN if user lacks permission."""

def require_step_up():
    """FastAPI dependency: raises 403 STEP_UP_REQUIRED if step_up_until is expired."""

def require_high_risk():
    """Combined: require super_admin + step-up. Raises appropriate 403."""
```

### Error Responses

| Code | Message |
|------|---------|
| 403 `PERMISSION_DENIED` | "Insufficient permissions for this operation" |
| 403 `STEP_UP_REQUIRED` | "Step-up authentication required for this operation" |

Both use generic messages — no hint about what permission is missing.

## File Structure

| File | Operation | Responsibility |
|------|-----------|---------------|
| `apps/api/app/services/rbac_service.py` | Create | Permission constants, role mapping, `has_permission`, `require_permission`, `require_step_up`, `require_high_risk` |
| `apps/api/app/dependencies/rbac.py` | Create | FastAPI dependency wrappers |
| `apps/api/tests/test_phase_web_3_rbac.py` | Create | Permission matrix tests |
| `reports/web_phase_3_report.md` | Create | Phase report |

## Security Requirements

- No role string comparison in routers: `if user.role == "admin"` → `has_permission(user, PERM_...)`
- Disabled users get 401 (not 403) from `get_current_session` — already handled in Phase 2.
- Permission check errors return generic messages.
- All high-risk operations (Phase 4+) will use `require_high_risk` dependency.

## Assumptions

- Phase 1: `User.role` and `User.is_disabled` exist.
- Phase 2: `DashboardSession.step_up_until` exists, `get_current_session` dependency exists.
- No endpoint-level permission guards are added in this phase — only the helper and dependencies.
