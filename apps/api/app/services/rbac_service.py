"""RBAC permission helpers: role-to-permission mapping and permission checks.

No role string comparison should appear in routers. All permission checks
go through has_permission() or the require_* dependencies.
"""
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_session import DashboardSession
from app.models.organization import Organization, OrganizationMember
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

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
PERM_APPROVE_ACCESS_REQUEST = "access_request:approve"
PERM_MODIFY_SECURITY_POLICY = "security:modify"
PERM_READ_SYSTEM = "system:read"
PERM_SUPER_ADMIN_WRITE = "super_admin:write"

# Admin general read (dashboard overview, egress logs, etc.)
PERM_ADMIN_READ = "admin:read"

# Policy management (admin read, super_admin manage)
PERM_POLICY_READ = "policy:read"
PERM_POLICY_MANAGE = "policy:manage"

# SLA monitoring
PERM_SLA_READ = "sla:read"
PERM_SLA_MANAGE = "sla:manage"

# Business continuity
PERM_CONTINUITY_READ = "continuity:read"
PERM_CONTINUITY_MANAGE = "continuity:manage"

# Organization-scoped permissions (org domain). These are granted by
# OrganizationMember.role, NOT by the platform UserRole. The ':org' suffix
# marks them as organization-scoped so frontend guards can distinguish
# them from the global platform permissions above.
PERM_OVERVIEW_READ_ORG = "overview:read:org"
PERM_AGENT_READ_ORG = "agent:read:org"
PERM_TASK_READ_ORG = "task:read:org"
PERM_APPROVAL_HANDLE_ORG = "approval:handle:org"
PERM_CONNECTION_READ_ORG = "connection:read:org"
PERM_POLICY_READ_ORG = "policy:read:org"
PERM_SLA_READ_ORG = "sla:read:org"
PERM_AUDIT_READ_ORG = "audit:read:org"
PERM_ORG_MANAGE = "org:manage"

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
    PERM_ADMIN_READ,
    PERM_POLICY_READ,
    PERM_SLA_READ,
    PERM_CONTINUITY_READ,
}

_SUPER_ADMIN_PERMS: set[str] = _ADMIN_PERMS | {
    PERM_EXPORT_AUDIT, PERM_DISABLE_USER, PERM_DISABLE_AGENT,
    PERM_CANCEL_RUNNING_TASK, PERM_FORCE_REVOKE_KEYS,
    PERM_MODIFY_SECURITY_POLICY, PERM_READ_SYSTEM,
    PERM_SUPER_ADMIN_WRITE,
    PERM_POLICY_MANAGE,
    PERM_SLA_MANAGE,
    PERM_CONTINUITY_MANAGE,
    PERM_APPROVE_ACCESS_REQUEST,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    UserRole.USER.value: _USER_PERMS,
    UserRole.ADMIN.value: _ADMIN_PERMS,
    UserRole.SUPER_ADMIN.value: _SUPER_ADMIN_PERMS,
}

# ──────────────────────────────────────────────────────────────────
# Organization membership permissions (org domain)
# ──────────────────────────────────────────────────────────────────

# An org manager can read everything scoped to their organization and
# handle org-scoped approvals, plus manage the organization itself.
ORG_MANAGER_PERMISSIONS: list[str] = [
    PERM_OVERVIEW_READ_ORG,
    PERM_AGENT_READ_ORG,
    PERM_TASK_READ_ORG,
    PERM_APPROVAL_HANDLE_ORG,
    PERM_CONNECTION_READ_ORG,
    PERM_POLICY_READ_ORG,
    PERM_SLA_READ_ORG,
    PERM_AUDIT_READ_ORG,
    PERM_ORG_MANAGE,
]

# A plain org member (employee) gets read-only access to the org overview.
ORG_MEMBER_PERMISSIONS: list[str] = [
    PERM_OVERVIEW_READ_ORG,
]

ORG_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "manager": ORG_MANAGER_PERMISSIONS,
    "member": ORG_MEMBER_PERMISSIONS,
}


async def resolve_user_permissions(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Resolve the full permission list for a user.

    Platform role permissions (ROLE_PERMISSIONS, keyed by UserRole) are
    unioned with the org-domain permissions derived from the user's
    OrganizationMember rows. Only memberships of non-disabled
    organizations count — disabling an org revokes its permissions
    (fail-closed degradation path).

    Fail-closed: ANY exception while reading the membership table (or an
    unknown platform role) results in an empty permission list. Permission
    resolution must never silently degrade to a partial-but-elevated set.
    """
    try:
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None or user.is_disabled:
            return []

        platform_perms = ROLE_PERMISSIONS.get(user.role)
        if platform_perms is None:
            # Unknown platform role: refuse to resolve anything.
            logger.warning(
                "resolve_user_permissions: unknown role %r for user %s; "
                "returning no permissions",
                user.role,
                user_id,
            )
            return []

        perms: set[str] = set(platform_perms)

        # Org-domain permissions from membership rows. Memberships of
        # disabled organizations are excluded so that disabling an org
        # immediately revokes its permissions.
        member_result = await session.execute(
            select(OrganizationMember.role)
            .join(Organization, OrganizationMember.org_id == Organization.id)
            .where(
                OrganizationMember.user_id == user_id,
                Organization.is_disabled.is_(False),
            )
        )
        for (org_role,) in member_result.all():
            org_perms = ORG_ROLE_PERMISSIONS.get(org_role)
            if org_perms is None:
                # Unknown org role on a row: skip that row rather than
                # aborting the whole resolution, but log it.
                logger.warning(
                    "resolve_user_permissions: unknown org role %r for "
                    "user %s; skipping membership",
                    org_role,
                    user_id,
                )
                continue
            perms.update(org_perms)

        return sorted(perms)
    except Exception:
        # Fail-closed: any failure in permission resolution yields an
        # empty list rather than a partial or elevated one.
        logger.exception(
            "resolve_user_permissions: resolution failed for user %s; "
            "returning no permissions",
            user_id,
        )
        return []


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
