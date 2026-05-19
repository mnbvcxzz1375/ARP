"""Phase Web 1: User RBAC + Dashboard Sessions — model tests."""
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole
from app.models.dashboard_session import DashboardSession


class TestUserRBAC:
    """Tests for User role and is_disabled columns."""

    async def test_default_role_is_user(self, session: AsyncSession):
        """Newly created User defaults to role='user', is_disabled=false."""
        user = User(
            id=uuid.uuid4(),
            username=f"rbac-test-{uuid.uuid4().hex[:8]}",
        )
        session.add(user)
        await session.flush()

        assert user.role == UserRole.USER.value
        assert user.is_disabled is False

    async def test_role_string_value_matches_enum(self):
        """UserRole enum values match the expected DB strings."""
        assert UserRole.USER.value == "user"
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.SUPER_ADMIN.value == "super_admin"

    async def test_create_user_with_explicit_role(self, session: AsyncSession):
        """User can be created with an explicit admin role."""
        user = User(
            id=uuid.uuid4(),
            username=f"rbac-admin-{uuid.uuid4().hex[:8]}",
            role=UserRole.ADMIN.value,
        )
        session.add(user)
        await session.flush()

        assert user.role == "admin"

    async def test_check_constraint_rejects_invalid_role(self, session: AsyncSession):
        """Inserting a user with role='hacker' must raise IntegrityError."""
        uid = str(uuid.uuid4())
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO users (id, username, role) "
                    "VALUES (:uid, :username, 'hacker')"
                ),
                {"uid": uid, "username": f"rbac-badrole-{uid[:8]}"},
            )
            await session.flush()

    async def test_orm_defaults_match_server_defaults(self, session: AsyncSession):
        """ORM defaults for role and is_disabled match the migration server defaults."""
        result = await session.execute(
            text("SELECT COUNT(*) FROM users WHERE role <> 'user' OR is_disabled IS DISTINCT FROM false")
        )
        count = result.scalar_one()
        assert count == 0, f"Found {count} users with non-default role or is_disabled"

    async def test_is_disabled_can_be_toggled(self, session: AsyncSession):
        """User's is_disabled can be toggled to True and back."""
        user = User(
            id=uuid.uuid4(),
            username=f"rbac-disable-{uuid.uuid4().hex[:8]}",
        )
        session.add(user)
        await session.flush()
        assert user.is_disabled is False

        user.is_disabled = True
        await session.flush()
        await session.refresh(user)
        assert user.is_disabled is True

        user.is_disabled = False
        await session.flush()
        await session.refresh(user)
        assert user.is_disabled is False


class TestDashboardSession:
    """Tests for the DashboardSession model."""

    async def test_create_session(self, session: AsyncSession):
        """A DashboardSession can be created and flushed."""
        from datetime import datetime, timedelta, UTC

        user = User(
            id=uuid.uuid4(),
            username=f"dbsess-test-{uuid.uuid4().hex[:8]}",
        )
        session.add(user)
        await session.flush()

        now = datetime.now(UTC)
        ds = DashboardSession(
            id=uuid.uuid4(),
            user_id=user.id,
            session_hash="sha256_deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef",
            csrf_hash="sha256_feedfacecafebabe0123456789abcdef0123456789abcdef0123456789abcdef",
            expires_at=now + timedelta(days=7),
            idle_expires_at=now + timedelta(hours=2),
        )
        session.add(ds)
        await session.flush()

        assert ds.id is not None
        assert ds.user_id == user.id
        assert ds.session_hash.startswith("sha256_")

    async def test_session_hash_uniqueness(self, session: AsyncSession):
        """Two sessions with the same session_hash must raise IntegrityError."""
        from datetime import datetime, timedelta, UTC

        user = User(
            id=uuid.uuid4(),
            username=f"dbsess-unique-{uuid.uuid4().hex[:8]}",
        )
        session.add(user)
        await session.flush()

        now = datetime.now(UTC)
        same_hash = "sha256_duplicatehash_1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

        ds1 = DashboardSession(
            id=uuid.uuid4(),
            user_id=user.id,
            session_hash=same_hash,
            csrf_hash="sha256_csrf1_1234567890abcdef",
            expires_at=now + timedelta(days=1),
            idle_expires_at=now + timedelta(hours=1),
        )
        session.add(ds1)
        await session.flush()

        ds2 = DashboardSession(
            id=uuid.uuid4(),
            user_id=user.id,
            session_hash=same_hash,
            csrf_hash="sha256_csrf2_1234567890abcdef",
            expires_at=now + timedelta(days=1),
            idle_expires_at=now + timedelta(hours=1),
        )
        session.add(ds2)

        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_fk_cascade_user_delete_removes_sessions(self, session: AsyncSession):
        """Deleting a user must cascade-delete their sessions."""
        from datetime import datetime, timedelta, UTC

        user = User(
            id=uuid.uuid4(),
            username=f"dbsess-cascade-{uuid.uuid4().hex[:8]}",
        )
        session.add(user)
        await session.flush()

        now = datetime.now(UTC)
        ds = DashboardSession(
            id=uuid.uuid4(),
            user_id=user.id,
            session_hash="sha256_cascade_test_hash_0123456789abcdef0123456789abcdef0123456789abcdef01",
            csrf_hash="sha256_csrf_cascade_0123456789abcdef",
            expires_at=now + timedelta(days=1),
            idle_expires_at=now + timedelta(hours=1),
        )
        session.add(ds)
        await session.flush()
        session_id = ds.id

        # Delete the user (ORM level — will cascade)
        await session.delete(user)
        await session.flush()

        # Verify session is gone
        result = await session.execute(
            select(DashboardSession).where(DashboardSession.id == session_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_fk_set_null_revoker_deleted(self, session: AsyncSession):
        """Deleting the revoker must SET NULL on revoked_by_user_id."""
        from datetime import datetime, timedelta, UTC

        revoker = User(
            id=uuid.uuid4(),
            username=f"dbsess-revoker-{uuid.uuid4().hex[:8]}",
        )
        session.add(revoker)

        target_user = User(
            id=uuid.uuid4(),
            username=f"dbsess-target-{uuid.uuid4().hex[:8]}",
        )
        session.add(target_user)
        await session.flush()

        now = datetime.now(UTC)
        ds = DashboardSession(
            id=uuid.uuid4(),
            user_id=target_user.id,
            session_hash="sha256_setnull_test_hash_0123456789abcdef0123456789abcdef0123456789abcdef01",
            csrf_hash="sha256_csrf_setnull_0123456789abcdef",
            expires_at=now + timedelta(days=1),
            idle_expires_at=now + timedelta(hours=1),
            revoked_at=now,
            revoked_reason="admin_revoke",
            revoked_by_user_id=revoker.id,
        )
        session.add(ds)
        await session.flush()

        # Delete the revoker
        await session.delete(revoker)
        await session.flush()

        # Verify revoked_by_user_id is NULL but session still exists
        await session.refresh(ds)
        assert ds.revoked_by_user_id is None
        assert ds.id is not None
