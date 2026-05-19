"""RBAC permission helpers: role-to-permission mapping and permission checks.

No role string comparison should appear in routers. All permission checks
go through has_permission() or the require_* dependencies.
"""
from datetime import UTC, datetime

from app.models.user import User, UserRole
from app.models.dashboard_session import DashboardSession

# ──────────────────────────────────────────────────────────────────
# Permission constants
# ──────────────────────────────────────────────────────────────────

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

# ──────────────────────────────────────────────────────────────────
# Role-to-permission mapping
# ──────────────────────────────────────────────────────────────────

_USER_PERMS: set[str] = {
    PERM_READ_OWN_AGENTS, PERM_CREATE_AGENT, PERM_EDIT_OWN_AGENT,
    PERM_DELETE_OWN_AGENT, PERM_ROTATE_OWN_TOKEN,
    PERM_READ_OWN_TASKS, PERM_CREATE_TASK, PERM_READ_OWN_TASK_DETAIL,
    PERM_HANDLE_OWN_APPROVAL,
    PERM_MANAGE_OWN_CONNECTIONS, PERM_MANAGE_OWN_FIREWALL,
    PERM_MANAGE_OWN_KEYS,
}

_ADMIN_PERMS: set[str] = _USER_PERMS | {
    PERM_READ_GLOBAL_OVERVIEW, PERM_READ_GLOBAL_USERS,
    PERM_READ_GLOBAL_AGENTS, PERM_READ_GLOBAL_TASKS,
    PERM_READ_GLOBAL_TASK_DETAIL, PERM_READ_AUDIT_LOGS,
    PERM_CANCEL_PENDING_TASK,
}

_SUPER_ADMIN_PERMS: set[str] = _ADMIN_PERMS | {
    PERM_EXPORT_AUDIT, PERM_DISABLE_USER, PERM_DISABLE_AGENT,
    PERM_CANCEL_RUNNING_TASK, PERM_FORCE_REVOKE_KEYS,
    PERM_MODIFY_SECURITY_POLICY, PERM_READ_SYSTEM,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    UserRole.USER.value: _USER_PERMS,
    UserRole.ADMIN.value: _ADMIN_PERMS,
    UserRole.SUPER_ADMIN.value: _SUPER_ADMIN_PERMS,
}


def has_permission(user: User, permission: str) -> bool:
    """Check if user has the given permission.

    Returns False for disabled users or unknown permissions.
    """
    if user.is_disabled:
        return False
    perms = ROLE_PERMISSIONS.get(user.role)
    if perms is None:
        return False
    return permission in perms


def has_step_up(ds: DashboardSession) -> bool:
    """Check if session has valid step-up auth window."""
    if ds.step_up_until is None:
        return False
    return ds.step_up_until > datetime.now(UTC)
