"""Phase Web 3: RBAC permission helpers — unit tests."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.user import User, UserRole
from app.models.dashboard_session import DashboardSession
from app.services.rbac_service import (
    has_permission,
    has_step_up,
    ROLE_PERMISSIONS,
    PERM_READ_OWN_AGENTS,
    PERM_CREATE_AGENT,
    PERM_READ_GLOBAL_USERS,
    PERM_READ_GLOBAL_AGENTS,
    PERM_DISABLE_USER,
    PERM_EXPORT_AUDIT,
    PERM_READ_SYSTEM,
    _USER_PERMS,
    _ADMIN_PERMS,
    _SUPER_ADMIN_PERMS,
)


class TestRoleHierarchy:
    """Verify the permission hierarchy is strictly nested."""

    def test_user_perms_subset_of_admin(self):
        assert _USER_PERMS.issubset(_ADMIN_PERMS)

    def test_admin_perms_subset_of_super_admin(self):
        assert _ADMIN_PERMS.issubset(_SUPER_ADMIN_PERMS)

    def test_role_permissions_map_matches_sets(self):
        assert ROLE_PERMISSIONS[UserRole.USER.value] == _USER_PERMS
        assert ROLE_PERMISSIONS[UserRole.ADMIN.value] == _ADMIN_PERMS
        assert ROLE_PERMISSIONS[UserRole.SUPER_ADMIN.value] == _SUPER_ADMIN_PERMS


class TestHasPermission:
    """Tests for has_permission() function."""

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
        for perm in _SUPER_ADMIN_PERMS:
            assert has_permission(user, perm) is True

    def test_disabled_user_has_no_perms(self):
        user = User(
            id=uuid.uuid4(), username="disabled",
            role=UserRole.SUPER_ADMIN.value, is_disabled=True,
        )
        assert has_permission(user, PERM_READ_OWN_AGENTS) is False
        assert has_permission(user, PERM_DISABLE_USER) is False

    def test_unknown_role_has_no_perms(self):
        user = User(id=uuid.uuid4(), username="weird", role="unknown_role")
        assert has_permission(user, PERM_READ_OWN_AGENTS) is False

    def test_every_perm_accessible_by_at_least_one_role(self):
        """Sanity: no permission constant is completely orphaned."""
        all_perms = _USER_PERMS | _ADMIN_PERMS | _SUPER_ADMIN_PERMS
        for perm in all_perms:
            found = any(perm in perms for perms in ROLE_PERMISSIONS.values())
            assert found, f"Permission {perm!r} not assigned to any role"


class TestHasStepUp:
    """Tests for has_step_up() function."""

    def test_no_step_up_returns_false(self):
        ds = DashboardSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(),
            session_hash="x", csrf_hash="y", step_up_until=None,
        )
        assert has_step_up(ds) is False

    def test_expired_step_up_returns_false(self):
        ds = DashboardSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(),
            session_hash="x", csrf_hash="y",
            step_up_until=datetime.now(UTC) - timedelta(minutes=1),
        )
        assert has_step_up(ds) is False

    def test_valid_step_up_returns_true(self):
        ds = DashboardSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(),
            session_hash="x", csrf_hash="y",
            step_up_until=datetime.now(UTC) + timedelta(minutes=5),
        )
        assert has_step_up(ds) is True

    def test_exactly_now_returns_false(self):
        """Edge case: step_up_until == now should be False (not >)."""
        ds = DashboardSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(),
            session_hash="x", csrf_hash="y",
            step_up_until=datetime.now(UTC),
        )
        assert has_step_up(ds) is False
