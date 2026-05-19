# Phase 1 Design: User RBAC + Dashboard Sessions

**Date**: 2026-05-18
**Status**: Review Ready
**Scope**: AgentNet Enterprise Dashboard — Phase 1 of 13
**Revises**: 0008_fix_idempotency_scope

## Summary

Add RBAC columns to the `users` table and create the `dashboard_sessions` table. This is the database foundation for Dashboard authentication, role-based access control, CSRF protection, and session lifecycle management defined in web.md Section 4.

No API endpoints or service logic are delivered in this phase — only the data model and migration.

## User Model Changes

### New Fields

```python
# apps/api/app/models/user.py

from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class User(Base):
    # --- existing fields unchanged ---

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserRole.USER.value,
        server_default=sa.text("'user'"),
        index=True,
    )
    is_disabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )

    # Relationships (existing + new)
    dashboard_sessions: Mapped[list["DashboardSession"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="DashboardSession.user_id",
    )
    revoked_dashboard_sessions: Mapped[list["DashboardSession"]] = relationship(
        back_populates="revoked_by",
        lazy="selectin",
        foreign_keys="DashboardSession.revoked_by_user_id",
    )
```

### Constraints

- **Check constraint**: `role IN ('user', 'admin', 'super_admin')` enforced at DB level via `ck_users_role_valid`.
- **Default**: All existing users get `role='user'`, `is_disabled=false`. No existing user is accidentally locked out or escalated.
- **No DB enum type**: Uses `String(32)` instead of PostgreSQL enum. New roles must be added via explicit migration, preventing "role drift" without review.

### Migration Verification

After migration, the following query MUST return `0`:

```sql
SELECT COUNT(*) FROM users
WHERE role <> 'user' OR is_disabled IS DISTINCT FROM false;
```

## DashboardSessions Model

### Table: `dashboard_sessions`

```python
# apps/api/app/models/dashboard_session.py

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class DashboardSession(Base):
    __tablename__ = "dashboard_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    # Only hash stored — never plaintext token
    session_hash: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    # Format not fixed; may include algorithm prefix in future
    csrf_hash: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_csrf_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    step_up_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    request_ip: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="dashboard_sessions",
        foreign_keys=[user_id],
    )
    revoked_by: Mapped["User | None"] = relationship(
        back_populates="revoked_dashboard_sessions",
        foreign_keys=[revoked_by_user_id],
    )
```

### Index Plan

| Index | Type | Columns | Purpose |
|-------|------|---------|---------|
| `ix_dashboard_sessions_user_id` | INDEX | `user_id` | Find all sessions for a user; created explicitly because PostgreSQL does not auto-index foreign keys |
| `uq_dashboard_sessions_session_hash` | UNIQUE | `session_hash` | Lookup session by hash |
| `ix_dashboard_sessions_revoked_at` | INDEX | `revoked_at` | Exclude revoked sessions |
| `ix_dashboard_sessions_expires_at` | INDEX | `expires_at` | Cleanup expired sessions |
| `ix_dashboard_sessions_step_up_until` | INDEX | `step_up_until` | Check step-up validity |
| `ix_dashboard_sessions_revoked_by_user_id` | INDEX | `revoked_by_user_id` | Audit: who revoked what |
| `ix_dashboard_sessions_user_revoked` | COMPOSITE | `(user_id, revoked_at)` | Dashboard: user's active sessions |
| `ix_dashboard_sessions_user_expires` | COMPOSITE | `(user_id, expires_at)` | Dashboard: user's expiring sessions |

### `revoked_reason` Allowed Values

The column is `String(256)` but the service layer (Phase 2+) MUST restrict to these enum values:

| Value | Semantics |
|-------|-----------|
| `logout` | User-initiated logout |
| `expired` | Absolute lifetime expired |
| `idle_timeout` | Idle timeout reached |
| `role_changed` | User role modified (security rotation) |
| `user_disabled` | User disabled by admin |
| `api_key_revoked` | User's API key force-revoked |
| `admin_revoke` | Administrator revoked session |
| `session_rotated` | Session rotated (step-up, re-login) |
| `security_event` | Security incident response |

### `last_seen_at` Write Throttling

The field exists in the model, but the service layer (Phase 2+) MUST throttle writes: update only if `now - last_seen_at > 60s`. This prevents DB write amplification from Dashboard short-polling (15s user, 30s admin).

## Migration

### File

`apps/api/migrations/versions/0009_phase_web_1_rbac_sessions.py`

### `upgrade()`

1. Add `role` column with check constraint + index
2. Add `is_disabled` column
3. Create `dashboard_sessions` table
4. Create all indexes and unique constraint

### `downgrade()` (explicit order for production audit)

1. Drop `dashboard_sessions` composite indexes
2. Drop `dashboard_sessions` unique constraint
3. Drop `dashboard_sessions` single-column indexes
4. Drop `dashboard_sessions` table
5. Drop `ck_users_role_valid` constraint
6. Drop `ix_users_role` index
7. Drop `is_disabled` column
8. Drop `role` column

## Delivery Checklist

### Files Changed/Created

| File | Operation |
|------|-----------|
| `apps/api/app/models/user.py` | Add `UserRole` enum, `role`, `is_disabled`, DashboardSession relationships |
| `apps/api/app/models/dashboard_session.py` | NEW — DashboardSession ORM |
| `apps/api/app/models/__init__.py` | Register DashboardSession |
| `apps/api/migrations/versions/0009_phase_web_1_rbac_sessions.py` | NEW — migration |
| `tests/test_phase_web_1_rbac.py` | NEW — model + migration tests |
| `reports/web_phase_1_report.md` | NEW — phase report |

### Test Coverage

| Test | What It Verifies |
|------|-----------------|
| Default role on new user | `role='user'`, `is_disabled=false` |
| Check constraint: invalid role rejected | `role='hacker'` raises IntegrityError |
| Check constraint: valid roles accepted | `user`, `admin`, `super_admin` all insert |
| session_hash uniqueness | Duplicate hash raises IntegrityError |
| FK cascade: user deleted → sessions deleted | Delete user, verify sessions gone |
| FK SET NULL: revoker deleted → revoked_by_user_id null | Delete revoker, verify column NULL |
| Migration repeat no-op | `alembic upgrade head` twice — second run performs no migration and returns success |
| Migration reversibility | `alembic downgrade 0008_fix_idempotency_scope` then `alembic upgrade head` succeeds |
| Existing users after migration | All `role='user'`, all `is_disabled=false` |

### Verification Commands

```bash
# Apply migration
docker compose -f infra/docker-compose.yml run --rm api alembic upgrade head

# Verify table structure
docker exec infra-postgres-1 psql -U agentnet -d agentnet -c "\d users"
docker exec infra-postgres-1 psql -U agentnet -d agentnet -c "\d dashboard_sessions"

# Verify existing users default role
docker exec infra-postgres-1 psql -U agentnet -d agentnet \
  -c "SELECT role, is_disabled, COUNT(*) FROM users GROUP BY role, is_disabled;"
# Expected: one row: role='user', is_disabled=false, count = N

# Verify check constraint blocks invalid role
docker exec infra-postgres-1 psql -U agentnet -d agentnet <<'SQL'
BEGIN;
INSERT INTO users (id, username, role)
VALUES ('00000000-0000-0000-0000-000000000901', '_ck_test_user', 'hacker');
ROLLBACK;
SQL
# Expected: ERROR: new row violates check constraint "ck_users_role_valid"

# Verify migration is reversible
docker compose -f infra/docker-compose.yml run --rm api alembic downgrade 0008_fix_idempotency_scope
docker compose -f infra/docker-compose.yml run --rm api alembic upgrade head
```

## Assumptions

- No existing code depends on `User` not having these columns.
- `session_hash` format is caller's responsibility (SHA-256 hex in production).
- `csrf_hash` format is caller's responsibility.
- Migration is backward-compatible: existing API key-based REST API continues working.
