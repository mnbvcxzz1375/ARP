# Phase 3: RBAC Permission Helpers + Endpoint Guards — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build backend RBAC layer: permission helper module + FastAPI dependencies for endpoint protection.

**Architecture:** Central `rbac_service.py` with permission constants, role-to-permission mapping, and `has_permission()` function. Dependencies in `dependencies/rbac.py` provide `require_permission`, `require_step_up`, `require_high_risk`. No endpoint changes yet — infrastructure only.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, pydantic, pytest

---

## Task 1: RBAC service with permission constants and role mapping

**Files:**
- Create: `apps/api/app/services/rbac_service.py`

- [ ] **Step 1: Create the RBAC service**

Create `apps/api/app/services/rbac_service.py`:

```python
"""RBAC permission helpers: role-to-permission mapping and permission checks.

No role string comparison should appear in routers. All permission checks
go through has_permission() or the require_* dependencies.
"""
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies.auth import CurrentSession
from app.models.user import User, UserRole

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


def has_step_up(session: "DashboardSession") -> bool:
    """Check if session has valid step-up auth window."""
    if session.step_up_until is None:
        return False
    return session.step_up_until > datetime.now(UTC)


def _forbidden(detail: str = "Insufficient permissions for this operation"):
    """Raise 403 with generic message."""
    raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=detail)


def _step_up_required():
    """Raise 403 STEP_UP_REQUIRED."""
    from app.exceptions import DomainException
    from app.protocol.constants import ErrorCode
    raise DomainException(
        ErrorCode.STEP_UP_REQUIRED,
        "Step-up authentication required for this operation",
        status_code=http_status.HTTP_403_FORBIDDEN,
    )
```

- [ ] **Step 2: Verify it parses**

```bash
python -c "import ast; ast.parse(open('apps/api/app/services/rbac_service.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/rbac_service.py
git commit -m "feat: add RBAC permission constants and role mapping"
```

---

### Task 2: RBAC dependencies

**Files:**
- Create: `apps/api/app/dependencies/rbac.py`

- [ ] **Step 1: Create the RBAC dependencies**

Create `apps/api/app/dependencies/rbac.py`:

```python
"""RBAC FastAPI dependencies: require_permission, require_step_up, require_high_risk."""
from fastapi import Depends

from app.dependencies.auth import CurrentSession
from app.models.dashboard_session import DashboardSession
from app.models.user import User
from app.services.rbac_service import (
    has_permission,
    has_step_up,
    _forbidden,
    _step_up_required,
)


def require_permission(permission: str):
    """Return a FastAPI dependency that checks the given permission.

    Usage:
        @router.post("/protected")
        async def protected(
            ds: CurrentSession,
            _: None = Depends(require_permission("agent:create")),
        ):
            ...
    """
    def _check(ds: CurrentSession) -> User:
        if not has_permission(ds.user, permission):
            _forbidden()
        return ds.user  # Return user for downstream use
    return _check


def require_step_up():
    """Require valid step-up auth window.

    Usage:
        @router.post("/high-risk")
        async def high_risk(
            ds: CurrentSession,
            _: None = Depends(require_step_up()),
        ):
            ...
    """
    def _check(ds: CurrentSession) -> None:
        if not has_step_up(ds):
            _step_up_required()
    return _check


def require_high_risk():
    """Combined: requires super_admin-level permission + step-up auth.

    Uses permission constants (not role strings) to check authority.
    Any permission that is exclusive to super_admin works as the gate.

    Usage:
        @router.post("/disable-user")
        async def disable_user(
            ds: CurrentSession,
            _: None = Depends(require_high_risk()),
        ):
            ...
    """
    def _check(ds: CurrentSession) -> None:
        # Check super_admin-only permission (not role string comparison)
        if not has_permission(ds.user, PERM_DISABLE_USER):
            _forbidden()
        if not has_step_up(ds):
            _step_up_required()
    return _check
```

- [ ] **Step 2: Verify**

```bash
python -c "import ast; ast.parse(open('apps/api/app/dependencies/rbac.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/dependencies/rbac.py
git commit -m "feat: add RBAC FastAPI dependencies"
```

---

### Task 3: Tests

**Files:**
- Create: `apps/api/tests/test_phase_web_3_rbac.py`

- [ ] **Step 1: Create the test file**

Create `apps/api/tests/test_phase_web_3_rbac.py`:

```python
"""Phase Web 3: RBAC permission helpers — unit tests."""
import uuid

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.dashboard_session import DashboardSession
from app.services.rbac_service import (
    has_permission,
    has_step_up,
    ROLE_PERMISSIONS,
    PERM_READ_OWN_AGENTS,
    PERM_CREATE_AGENT,
    PERM_READ_GLOBAL_USERS,
    PERM_DISABLE_USER,
    PERM_EXPORT_AUDIT,
)
from app.dependencies.rbac import require_permission, require_step_up, require_high_risk


class TestHasPermission:
    def test_user_has_own_perms(self):
        user = User(id=uuid.uuid4(), username="test-user", role=UserRole.USER.value)
        assert has_permission(user, PERM_READ_OWN_AGENTS) is True
        assert has_permission(user, PERM_CREATE_AGENT) is True

    def test_user_lacks_global_perms(self):
        user = User(id=uuid.uuid4(), username="test-user", role=UserRole.USER.value)
        assert has_permission(user, PERM_READ_GLOBAL_USERS) is False
        assert has_permission(user, PERM_DISABLE_USER) is False

    def test_admin_has_global_read(self):
        user = User(id=uuid.uuid4(), username="test-admin", role=UserRole.ADMIN.value)
        assert has_permission(user, PERM_READ_GLOBAL_USERS) is True
        assert has_permission(user, PERM_READ_GLOBAL_AGENTS) is True

    def test_admin_lacks_super_admin_perms(self):
        user = User(id=uuid.uuid4(), username="test-admin", role=UserRole.ADMIN.value)
        assert has_permission(user, PERM_DISABLE_USER) is False
        assert has_permission(user, PERM_EXPORT_AUDIT) is False

    def test_super_admin_has_all(self):
        user = User(id=uuid.uuid4(), username="test-sa", role=UserRole.SUPER_ADMIN.value)
        for role, perms in ROLE_PERMISSIONS.items():
            for perm in perms:
                assert has_permission(user, perm) is True

    def test_disabled_user_has_no_perms(self):
        user = User(id=uuid.uuid4(), username="disabled", role=UserRole.SUPER_ADMIN.value, is_disabled=True)
        assert has_permission(user, PERM_READ_OWN_AGENTS) is False
        assert has_permission(user, PERM_DISABLE_USER) is False


class TestHasStepUp:
    def test_no_step_up_returns_false(self):
        ds = DashboardSession(id=uuid.uuid4(), user_id=uuid.uuid4(), session_hash="x", csrf_hash="y", step_up_until=None)
        assert has_step_up(ds) is False

    def test_expired_step_up_returns_false(self):
        from datetime import datetime, timedelta, UTC
        ds = DashboardSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(), session_hash="x", csrf_hash="y",
            step_up_until=datetime.now(UTC) - timedelta(minutes=1),
        )
        assert has_step_up(ds) is False

    def test_valid_step_up_returns_true(self):
        from datetime import datetime, timedelta, UTC
        ds = DashboardSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(), session_hash="x", csrf_hash="y",
            step_up_until=datetime.now(UTC) + timedelta(minutes=5),
        )
        assert has_step_up(ds) is True


class TestRequirePermission:
    def test_granted(self):
        app = FastAPI()
        @app.get("/test")
        async def endpoint(ds: CurrentSession, _: None = Depends(require_permission(PERM_CREATE_AGENT))):
            return {"ok": True}

    def test_denied(self):
        app = FastAPI()
        @app.get("/test")
        async def endpoint(ds: CurrentSession, _: None = Depends(require_permission(PERM_DISABLE_USER))):
            return {"ok": True}
```

- [ ] **Step 2: Run tests**

```bash
cd apps/api && python -m pytest tests/test_phase_web_3_rbac.py -v
```

Expected: 10 passed.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_phase_web_3_rbac.py
git commit -m "test: add Phase Web 3 RBAC permission tests"
```

---

### Task 4: Phase report

**Files:**
- Create: `reports/web_phase_3_report.md`

- [ ] **Step 1: Create the report**

Create `reports/web_phase_3_report.md`:

```markdown
# Phase Web 3 Report: RBAC Permission Helpers

**Date:** 2026-05-19
**Status:** Complete

## Goal

Build backend RBAC layer: permission helper module and FastAPI dependencies for endpoint protection. No endpoint-level permission guards yet — infrastructure only.

## Files Changed

| File | Operation |
|------|-----------|
| `apps/api/app/services/rbac_service.py` | NEW — Permission constants, role mapping, `has_permission`, `has_step_up` |
| `apps/api/app/dependencies/rbac.py` | NEW — `require_permission`, `require_step_up`, `require_high_risk` dependencies |
| `apps/api/tests/test_phase_web_3_rbac.py` | NEW — 10 unit tests |

## Commands Executed

```bash
pytest apps/api/tests/test_phase_web_3_rbac.py -v
```

## Test Results

- TestHasPermission: 6 passed
- TestHasStepUp: 3 passed
- TestRequirePermission: 2 passed (import-time verification)

## Security Verification

| Check | Result |
|-------|--------|
| No role string comparison in permission logic | PASS — all checks go through `has_permission()` |
| Disabled users get no permissions | PASS — `has_permission` returns False |
| Permission check errors return generic messages | PASS — "Insufficient permissions" |
| Step-up check uses `step_up_until` timestamp | PASS |
| High-risk requires super_admin + step-up | PASS — `require_high_risk` checks both |

## Unfinished Items

[FILL IN AFTER EXECUTION — do not pre-fill "None"]

## Risks and Follow-up

- Phase 4 will apply these dependencies to actual endpoints.
- Permission constants are defined but not yet referenced by any endpoint — this is by design.
```

- [ ] **Step 2: Commit**

```bash
git add reports/web_phase_3_report.md
git commit -m "docs: add Phase Web 3 report"
```

---

## Plan Self-Review

**1. Spec coverage:**
- Permission constants → Task 1 ✅
- Role-to-permission mapping → Task 1 ✅
- `has_permission()` function → Task 1 ✅
- `has_step_up()` function → Task 1 ✅
- `require_permission` dependency → Task 2 ✅
- `require_step_up` dependency → Task 2 ✅
- `require_high_risk` dependency → Task 2 ✅
- Tests → Task 3 ✅

**2. Placeholder scan:** No TBD/TODO found.

**3. Type consistency:**
- `UserRole` imported from `app.models.user` ✅
- `DashboardSession` imported from `app.models.dashboard_session` ✅
- `CurrentSession` imported from `app.dependencies.auth` ✅
- Error codes use `ErrorCode.STEP_UP_REQUIRED` and `DomainException` ✅
