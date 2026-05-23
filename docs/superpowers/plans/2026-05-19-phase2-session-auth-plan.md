# Phase 2: Session/Auth/CSRF/Step-Up Infrastructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build backend session management, authentication endpoints, and CSRF protection for the Dashboard.

**Architecture:** Session tokens and CSRF tokens stored as hashes only in `dashboard_sessions` table. Auth via HttpOnly cookies. Four auth endpoints (login, logout, step-up, me). CSRF middleware on all POST/PUT/PATCH/DELETE. No frontend yet — API only.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, pydantic-settings, hashlib (SHA-256), secrets (token generation), pytest

---

## File Structure

| File | Operation | Responsibility |
|------|-----------|---------------|
| `apps/api/app/config.py` | Modify | Add session lifetime and cookie settings |
| `apps/api/app/protocol/constants.py` | Modify | Add dashboard error codes |
| `apps/api/app/services/session_service.py` | Create | Session CRUD, rotation, revocation, validation |
| `apps/api/app/services/csrf_service.py` | Create | CSRF token generation and validation |
| `apps/api/app/dependencies/auth.py` | Create | `get_current_session` dependency |
| `apps/api/app/dependencies/csrf.py` | Create | `require_csrf` dependency |
| `apps/api/app/routers/dashboard_auth.py` | Create | Login, logout, step-up, me endpoints |
| `apps/api/app/main.py` | Modify | Register dashboard_auth router, add CSRF middleware |
| `apps/api/tests/test_phase_web_2_session.py` | Create | Auth/session/CSRF tests |
| `reports/web_phase_2_report.md` | Create | Phase report |

---

### Task 1: Add session config and error codes

**Files:**
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/app/protocol/constants.py`

- [ ] **Step 1: Add session config to Settings**

Add to `apps/api/app/config.py`, before `model_config`:

```python
    # Phase Web 2: Dashboard session management
    session_cookie_name: str = Field(
        default="agentnet_session", alias="SESSION_COOKIE_NAME",
    )
    csrf_cookie_name: str = Field(
        default="agentnet_csrf", alias="CSRF_COOKIE_NAME",
    )
    session_secure_cookie: bool = Field(
        default=False, alias="SESSION_SECURE_COOKIE",
        description="Set Secure flag on session cookies (true in production)",
    )
    session_user_lifetime_days: int = Field(
        default=30, alias="SESSION_USER_LIFETIME_DAYS",
    )
    session_admin_lifetime_days: int = Field(
        default=7, alias="SESSION_ADMIN_LIFETIME_DAYS",
    )
    session_user_idle_hours: int = Field(
        default=24, alias="SESSION_USER_IDLE_HOURS",
    )
    session_admin_idle_hours: int = Field(
        default=2, alias="SESSION_ADMIN_IDLE_HOURS",
    )
    session_step_up_duration_minutes: int = Field(
        default=10, alias="SESSION_STEP_UP_DURATION_MINUTES",
    )
```

- [ ] **Step 2: Add dashboard error codes**

Add to `ErrorCode` enum in `apps/api/app/protocol/constants.py` (before `MESSAGE_TYPES`):

```python
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    USER_DISABLED = "USER_DISABLED"
    CSRF_TOKEN_MISSING = "CSRF_TOKEN_MISSING"
    CSRF_TOKEN_INVALID = "CSRF_TOKEN_INVALID"
    INVALID_STEP_UP = "INVALID_STEP_UP"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    INVALID_SESSION = "INVALID_SESSION"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/config.py apps/api/app/protocol/constants.py
git commit -m "feat: add dashboard session config and error codes"
```

---

### Task 2: Session service

**Files:**
- Create: `apps/api/app/services/session_service.py`

- [ ] **Step 1: Create the session service**

Create `apps/api/app/services/session_service.py`:

```python
"""Dashboard session management: create, validate, rotate, revoke."""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.dashboard_session import DashboardSession
from app.models.user import User, UserRole


def _hash_token(token: str) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(48)


def _session_lifetime(user: User) -> tuple[timedelta, timedelta]:
    """Return (absolute_lifetime, idle_timeout) based on user role."""
    settings = get_settings()
    if user.role == UserRole.ADMIN or user.role == UserRole.SUPER_ADMIN:
        absolute = timedelta(days=settings.session_admin_lifetime_days)
        idle = timedelta(hours=settings.session_admin_idle_hours)
    else:
        absolute = timedelta(days=settings.session_user_lifetime_days)
        idle = timedelta(hours=settings.session_user_idle_hours)
    return absolute, idle


async def create_session(
    session: AsyncSession,
    user: User,
    request_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[DashboardSession, str, str]:
    """Create a new session for the user.

    Returns (session, session_token, csrf_token).
    Only the hashes are stored; plain tokens are returned once for cookie-setting.
    """
    now = datetime.now(UTC)
    absolute, idle = _session_lifetime(user)
    token = _generate_token()
    csrf_token = secrets.token_urlsafe(32)

    ds = DashboardSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_hash=_hash_token(token),
        csrf_hash=_hash_token(csrf_token),
        expires_at=now + absolute,
        idle_expires_at=now + idle,
        request_ip=request_ip,
        user_agent=user_agent,
    )
    session.add(ds)
    await session.flush()
    return ds, token, csrf_token


async def find_session_by_token(
    session: AsyncSession,
    token: str,
) -> DashboardSession | None:
    """Look up a session by plain token (hashes for lookup).

    Returns None if not found, expired, revoked, or user disabled.
    Uses selectinload to eager-load the user relationship, preventing
    MissingGreenlet errors in async SQLAlchemy.
    """
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(DashboardSession)
        .options(selectinload(DashboardSession.user))
        .where(
            DashboardSession.session_hash == _hash_token(token),
            DashboardSession.revoked_at.is_(None),
            DashboardSession.expires_at > datetime.now(UTC),
            DashboardSession.idle_expires_at > datetime.now(UTC),
        )
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        return None

    # Check user not disabled (user is eager-loaded via selectinload)
    if ds.user is None or ds.user.is_disabled:
        return None

    return ds


async def rotate_session(
    session: AsyncSession,
    old_session: DashboardSession,
    reason: str = "session_rotated",
    request_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[DashboardSession, str, str]:
    """Revoke old session and create a new one for the same user.

    Returns (new_session, new_token, new_csrf_token).
    """
    from sqlalchemy import update

    now = datetime.now(UTC)

    # Revoke old session
    await session.execute(
        update(DashboardSession)
        .where(DashboardSession.id == old_session.id)
        .values(
            revoked_at=now,
            revoked_reason=reason,
        )
    )

    # Get user
    user_result = await session.execute(
        select(User).where(User.id == old_session.user_id)
    )
    user = user_result.scalar_one()

    # Create new session
    absolute, idle = _session_lifetime(user)
    token = _generate_token()
    csrf_token = secrets.token_urlsafe(32)

    new_ds = DashboardSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_hash=_hash_token(token),
        csrf_hash=_hash_token(csrf_token),
        expires_at=now + absolute,
        idle_expires_at=now + idle,
        request_ip=request_ip,
        user_agent=user_agent,
        rotated_at=now,
    )
    session.add(new_ds)
    await session.flush()
    return new_ds, token, csrf_token


async def revoke_session(
    session: AsyncSession,
    ds: DashboardSession,
    reason: str = "logout",
) -> None:
    """Revoke a single session."""
    ds.revoked_at = datetime.now(UTC)
    ds.revoked_reason = reason
    await session.flush()


async def revoke_all_sessions(
    session: AsyncSession,
    user_id: uuid.UUID,
    reason: str = "user_disabled",
) -> int:
    """Revoke all active sessions for a user. Returns count."""
    from sqlalchemy import update

    now = datetime.now(UTC)
    result = await session.execute(
        update(DashboardSession)
        .where(
            DashboardSession.user_id == user_id,
            DashboardSession.revoked_at.is_(None),
        )
        .values(
            revoked_at=now,
            revoked_reason=reason,
        )
    )
    await session.flush()
    return result.rowcount


async def update_last_seen(
    session: AsyncSession,
    ds: DashboardSession,
) -> None:
    """Update last_seen_at, throttled to avoid write amplification."""
    from datetime import timedelta

    if ds.last_seen_at is None or (
        datetime.now(UTC) - ds.last_seen_at > timedelta(seconds=60)
    ):
        ds.last_seen_at = datetime.now(UTC)
        settings = get_settings()
        is_admin = ds.user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        idle_hours = settings.session_admin_idle_hours if is_admin else settings.session_user_idle_hours
        ds.idle_expires_at = ds.last_seen_at + timedelta(hours=idle_hours)
        await session.flush()


async def set_step_up(
    session: AsyncSession,
    ds: DashboardSession,
) -> None:
    """Mark session as step-up verified."""
    settings = get_settings()
    ds.step_up_until = datetime.now(UTC) + timedelta(
        minutes=settings.session_step_up_duration_minutes
    )
    await session.flush()


async def get_session_info(
    session: AsyncSession,
    ds: DashboardSession,
) -> dict[str, Any]:
    """Return safe session info for /me response."""
    user_result = await session.execute(
        select(User).where(User.id == ds.user_id)
    )
    user = user_result.scalar_one()

    # Build permissions list from role
    permissions: list[str] = []
    if user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        permissions.extend([
            "admin:read",
            "admin:cancel_pending_tasks",
        ])
    if user.role == UserRole.SUPER_ADMIN:
        permissions.extend([
            "super_admin:disable_user",
            "super_admin:disable_agent",
            "super_admin:cancel_running_tasks",
            "super_admin:export_audit",
        ])

    return {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role,
        "permissions": permissions,
        "csrf_required": True,
        "session_expires_at": ds.expires_at,
        "step_up_until": ds.step_up_until,
    }
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/services/session_service.py
git commit -m "feat: add session management service"
```

---

### Task 3: CSRF service

**Files:**
- Create: `apps/api/app/services/csrf_service.py`

- [ ] **Step 1: Create the CSRF service**

Create `apps/api/app/services/csrf_service.py`:

```python
"""CSRF token validation."""
import hashlib
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.dashboard_session import DashboardSession
from app.protocol.constants import ErrorCode


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def validate_csrf(
    session: AsyncSession,
    ds: DashboardSession,
    csrf_token: str,
) -> None:
    """Validate CSRF token against session hash.

    Raises DomainException(CSRF_TOKEN_INVALID) or DomainException(CSRF_TOKEN_MISSING).
    Updates last_csrf_seen_at on success.
    """
    if not csrf_token:
        raise DomainException(
            ErrorCode.CSRF_TOKEN_MISSING,
            "CSRF token is missing from request headers",
            status_code=403,
        )

    if _hash_token(csrf_token) != ds.csrf_hash:
        raise DomainException(
            ErrorCode.CSRF_TOKEN_INVALID,
            "CSRF token is invalid",
            status_code=403,
        )

    ds.last_csrf_seen_at = datetime.now(UTC)
    await session.flush()
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/services/csrf_service.py
git commit -m "feat: add CSRF token validation service"
```

---

### Task 4: Auth dependency

**Files:**
- Create: `apps/api/app/dependencies/auth.py`

- [ ] **Step 1: Create auth dependency**

Create `apps/api/app/dependencies/auth.py`:

```python
"""Dashboard auth dependencies: extract session from cookie, require auth."""
from typing import Annotated

from fastapi import Cookie, Depends, Request
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import DomainException
from app.models.dashboard_session import DashboardSession
from app.protocol.constants import ErrorCode
from app.services.session_service import find_session_by_token, update_last_seen


async def get_session_token(
    session_token: Annotated[str | None, Cookie(alias="agentnet_session")] = None,
) -> str | None:
    return session_token


async def get_current_session(
    request: Request,
    session: AsyncSession = Depends(get_session),
    session_token: str | None = Depends(get_session_token),
) -> DashboardSession:
    """Extract and validate the current DashboardSession from cookie.

    Raises 401 if no cookie, session not found, expired, revoked, or user disabled.
    Updates last_seen_at on valid session.
    """
    if not session_token:
        raise DomainException(
            ErrorCode.INVALID_SESSION,
            "Session cookie not found",
            status_code=http_status.HTTP_401_UNAUTHORIZED,
        )

    ds = await find_session_by_token(session, session_token)
    if ds is None:
        raise DomainException(
            ErrorCode.SESSION_EXPIRED,
            "Session has expired or been revoked",
            status_code=http_status.HTTP_401_UNAUTHORIZED,
        )

    await update_last_seen(session, ds)
    await session.refresh(ds)
    return ds


CurrentSession = Annotated[DashboardSession, Depends(get_current_session)]
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/dependencies/auth.py
git commit -m "feat: add dashboard auth dependency"
```

---

### Task 5: CSRF dependency

**Files:**
- Create: `apps/api/app/dependencies/csrf.py`

- [ ] **Step 1: Create CSRF dependency**

Create `apps/api/app/dependencies/csrf.py`:

```python
"""Dashboard CSRF dependency: extract CSRF token from cookie, validate header."""
from typing import Annotated

from fastapi import Cookie, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_session
from app.models.dashboard_session import DashboardSession
from app.services.csrf_service import validate_csrf


async def get_csrf_cookie(
    csrf_token: Annotated[str | None, Cookie(alias="agentnet_csrf")] = None,
) -> str | None:
    return csrf_token


async def get_csrf_header(
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> str | None:
    return x_csrf_token


async def require_csrf(
    request: Request,
    session: AsyncSession = Depends(get_session),
    ds: DashboardSession = Depends(get_current_session),
    csrf_cookie: str | None = Depends(get_csrf_cookie),
    csrf_header: str | None = Depends(get_csrf_header),
) -> None:
    """Validate CSRF for mutation requests (POST/PUT/PATCH/DELETE).

    GET/HEAD/OPTIONS are exempt. Raises 403 on missing or invalid CSRF.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    await validate_csrf(session, ds, csrf_header or "")
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/dependencies/csrf.py
git commit -m "feat: add CSRF dependency"
```

---

### Task 6: Dashboard auth router

**Files:**
- Create: `apps/api/app/routers/dashboard_auth.py`

- [ ] **Step 1: Create the auth router**

Create `apps/api/app/routers/dashboard_auth.py`:

```python
"""Dashboard authentication endpoints: login, logout, step-up, me."""
import hashlib

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.dependencies.auth import CurrentSession, get_session_token
from app.dependencies.csrf import require_csrf
from app.exceptions import DomainException
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services.audit_service import write_audit
from app.services.session_service import (
    create_session,
    revoke_session,
    rotate_session,
    set_step_up,
)

router = APIRouter(
    prefix="/v1/dashboard/auth",
    tags=["dashboard-auth"],
    dependencies=[Depends(require_csrf)],
)


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def _set_cookies(
    response: Response,
    session_token: str,
    csrf_token: str,
) -> None:
    settings = get_settings()
    cookie_kwargs = {
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "secure": settings.session_secure_cookie,
    }
    response.set_cookie(key=settings.session_cookie_name, value=session_token, **cookie_kwargs)
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        path="/",
        secure=settings.session_secure_cookie,
    )


def _clear_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.delete_cookie(key=settings.csrf_cookie_name, path="/")


@router.post("/login")
async def login(
    body: dict,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate with username + API key, create session, set cookies."""
    username = body.get("username", "")
    api_key = body.get("api_key", "")

    if not username or not api_key:
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Username and API key are required",
            status_code=401,
        )

    key_hash = _hash_key(api_key)
    result = await session.execute(
        select(User).where(
            User.username == username,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Invalid credentials",
            status_code=401,
        )

    # Verify API key
    from app.models.api_key import ApiKey
    key_result = await session.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked == False,
        )
    )
    found_key = key_result.scalar_one_or_none()

    if found_key is None:
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Invalid credentials",
            status_code=401,
        )

    if user.is_disabled:
        raise DomainException(
            ErrorCode.USER_DISABLED,
            "Account has been disabled",
            status_code=403,
        )

    # Create session, write audit, then commit (single transaction)
    ds, token, csrf_token = await create_session(
        session,
        user,
        request_ip=None,
        user_agent=None,
    )

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(user.id),
        action="dashboard.login.success",
        resource_type="session",
        resource_id=str(ds.id),
    )
    await session.commit()

    # Set cookies on the Response object before returning dict
    # (FastAPI will merge dict response with Response cookies)
    _set_cookies(response, token, csrf_token)
    response.status_code = 200
    return {"message": "authenticated"}


@router.post("/logout")
async def logout(
    response: Response,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Revoke current session, clear cookies."""
    await revoke_session(session, ds, reason="logout")
    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.logout",
        resource_type="session",
        resource_id=str(ds.id),
    )
    await session.commit()

    _clear_cookies(response)
    response.status_code = 200
    return {"message": "logged out"}


@router.post("/step-up")
async def step_up(
    body: dict,
    response: Response,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Re-verify API key to extend step-up window."""
    api_key = body.get("api_key", "")
    if not api_key:
        raise DomainException(
            ErrorCode.INVALID_STEP_UP,
            "Invalid step-up credentials",
            status_code=403,
        )

    key_hash = _hash_key(api_key)
    from app.models.api_key import ApiKey
    key_result = await session.execute(
        select(ApiKey).where(
            ApiKey.user_id == ds.user_id,
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked == False,
        )
    )
    if key_result.scalar_one_or_none() is None:
        raise DomainException(
            ErrorCode.INVALID_STEP_UP,
            "Invalid step-up credentials",
            status_code=403,
        )

    # Rotate session and set step-up
    new_ds, token, csrf_token = await rotate_session(
        session, ds, reason="step_up",
    )
    await set_step_up(session, new_ds)

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.step_up.success",
        resource_type="session",
        resource_id=str(new_ds.id),
    )
    await session.commit()

    _set_cookies(response, token, csrf_token)
    response.status_code = 200
    return {"message": "step-up verified"}


@router.get("/me")
async def me(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Return current user and session info."""
    from app.services.session_service import get_session_info
    info = await get_session_info(session, ds)
    await session.commit()
    return info
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/routers/dashboard_auth.py
git commit -m "feat: add dashboard auth endpoints (login, logout, step-up, me)"
```

---

### Task 7: Register router and add CSRF to main.py

**Files:**
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Add import and router registration**

In `apps/api/app/main.py`, add import after existing router imports:

```python
from app.routers.dashboard_auth import router as dashboard_auth_router
```

And register the router after `approvals_router`:

```python
    app.include_router(dashboard_auth_router)
```

**Note:** CSRF is enforced at the router level via `dependencies=[Depends(require_csrf)]` on both `dashboard_auth_router`, `dashboard_user_router`, and `dashboard_admin_router`. This means every POST/PUT/PATCH/DELETE to `/v1/dashboard/*` and `/v1/dashboard/admin/*` automatically requires a valid `X-CSRF-Token` header. No separate middleware is needed.

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/main.py
git commit -m "feat: register dashboard auth router and CSRF middleware"
```

---

### Task 8: Write tests

**Files:**
- Create: `apps/api/tests/test_phase_web_2_session.py`

- [ ] **Step 1: Create the test file**

Create `apps/api/tests/test_phase_web_2_session.py` with these tests:

```python
"""Phase Web 2: Session/Auth/CSRF — endpoint and service tests."""
import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.api_key import ApiKey
from app.models.dashboard_session import DashboardSession
from app.services.session_service import (
    create_session, find_session_by_token,
    rotate_session, revoke_session, revoke_all_sessions,
)
from app.services.csrf_service import validate_csrf
from app.protocol.constants import ErrorCode


@pytest.fixture
async def user_with_key(session: AsyncSession):
    """Create a user with an API key."""
    user = User(
        id=uuid.uuid4(),
        username=f"web2-test-{uuid.uuid4().hex[:8]}",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_hash=hashlib.sha256(b"test-key-12345").hexdigest(),
        key_prefix="ak_test",
        name="test-key",
    )
    session.add(api_key)
    await session.flush()
    return user, api_key, b"test-key-12345"


class TestLogin:
    async def test_login_success(self, client: AsyncClient, user_with_key, session):
        user, _, plain_key = user_with_key
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        assert resp.status_code == 200
        # Check cookies set
        assert "agentnet_session" in resp.cookies
        assert "agentnet_csrf" in resp.cookies

    async def test_login_invalid_credentials(self, client: AsyncClient, user_with_key):
        _, _, _ = user_with_key
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": "nonexistent",
            "api_key": "wrong",
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_login_wrong_key(self, client: AsyncClient, user_with_key, session):
        user, _, _ = user_with_key
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": "wrong-key",
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_login_disabled_user(self, client: AsyncClient, user_with_key, session):
        user, _, plain_key = user_with_key
        user.is_disabled = True
        await session.flush()
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "USER_DISABLED"


class TestMe:
    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/v1/dashboard/auth/me")
        assert resp.status_code == 401

    async def test_me_authenticated(self, client: AsyncClient, user_with_key, session):
        user, _, plain_key = user_with_key
        # Login first
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        resp = await client.get("/v1/dashboard/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == user.username
        assert data["role"] == user.role
        assert data["csrf_required"] is True


class TestLogout:
    async def test_logout(self, client: AsyncClient, user_with_key, session):
        user, _, plain_key = user_with_key
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        resp = await client.post("/v1/dashboard/auth/logout")
        assert resp.status_code == 200
        # Verify session revoked
        result = await session.execute(
            select(DashboardSession).where(DashboardSession.user_id == user.id)
        )
        ds = result.scalar_one()
        assert ds.revoked_at is not None


class TestStepUp:
    async def test_step_up_success(self, client: AsyncClient, user_with_key, session):
        user, _, plain_key = user_with_key
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        resp = await client.post("/v1/dashboard/auth/step-up", json={
            "api_key": plain_key.decode(),
        })
        assert resp.status_code == 200
        # Verify new session cookie set
        assert "agentnet_session" in resp.cookies

    async def test_step_up_wrong_key(self, client: AsyncClient, user_with_key):
        user, _, _ = user_with_key
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": "test-key-12345",
        })
        resp = await client.post("/v1/dashboard/auth/step-up", json={
            "api_key": "wrong-key",
        })
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_STEP_UP"


class TestSessionService:
    async def test_create_and_find_session(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, token, csrf = await create_session(session, user)
        await session.flush()

        found = await find_session_by_token(session, token)
        assert found is not None
        assert found.id == ds.id

        # Should not find with wrong token
        not_found = await find_session_by_token(session, "wrong")
        assert not_found is None

    async def test_rotate_session(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, token, csrf = await create_session(session, user)
        await session.flush()

        new_ds, new_token, new_csrf = await rotate_session(session, ds)
        await session.flush()

        # Old session should be revoked
        await session.refresh(ds)
        assert ds.revoked_at is not None
        # New session should be findable
        found = await find_session_by_token(session, new_token)
        assert found is not None

    async def test_revoke_all_sessions(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        # Create two sessions
        ds1, _, _ = await create_session(session, user)
        ds2, _, _ = await create_session(session, user)
        await session.flush()

        count = await revoke_all_sessions(session, user.id, reason="test")
        await session.flush()
        assert count == 2

    async def test_disabled_user_cannot_find_session(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, token, _ = await create_session(session, user)
        await session.flush()

        user.is_disabled = True
        await session.flush()

        found = await find_session_by_token(session, token)
        assert found is None


class TestCSRF:
    async def test_valid_csrf(self, session: AsyncSession, user_with_key):
        import secrets
        user, _, _ = user_with_key
        from app.services.session_service import _hash_token
        ds, _, _ = await create_session(session, user)
        await session.flush()

        plain_csrf = secrets.token_urlsafe(32)
        ds.csrf_hash = _hash_token(plain_csrf)
        await session.flush()

        await validate_csrf(session, ds, plain_csrf)
        # Should not raise

    async def test_missing_csrf_raises(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, _, _ = await create_session(session, user)
        await session.flush()

        with pytest.raises(Exception):
            await validate_csrf(session, ds, "")
```

- [ ] **Step 2: Add test fixture for async HTTP client**

Add to `apps/api/tests/conftest.py`:

```python
from httpx import ASGITransport, AsyncClient

@pytest.fixture
async def client(app):
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 3: Run tests**

```bash
cd apps/api && python -m pytest tests/test_phase_web_2_session.py -v
```

Expected: 14 passed (4 login + 2 me + 1 logout + 2 step-up + 3 session service + 2 CSRF).

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/test_phase_web_2_session.py apps/api/tests/conftest.py
git commit -m "test: add Phase Web 2 auth/session/CSRF tests"
```

---

### Task 9: Phase report

**Files:**
- Create: `reports/web_phase_2_report.md`

- [ ] **Step 1: Create the report**

Create `reports/web_phase_2_report.md` following the Phase 1 report template. Include:

- Goal: Session/auth/CSRF infrastructure for Dashboard
- Files changed table
- Commands executed
- Test results (expected 14 passed)
- Failure path verification (invalid login, disabled user, wrong step-up, missing CSRF)
- Security verification (no plain tokens in DB, generic error messages, cookie flags)
- Unfinished items: [FILL IN AFTER EXECUTION — do not pre-fill "None"]

- [ ] **Step 2: Commit**

```bash
git add reports/web_phase_2_report.md
git commit -m "docs: add Phase Web 2 report"
```

---

## Plan Self-Review

**1. Spec coverage:**
- Login/logout/step-up/me endpoints → Task 6 ✅
- Session CRUD/rotation/revocation → Task 2 ✅
- CSRF validation → Task 3 + Task 5 ✅
- Cookie policy (HttpOnly, SameSite, Secure) → Task 6 ✅
- Role-based lifetimes → Task 2 ✅
- Audit logging → Task 6 ✅
- Config settings → Task 1 ✅
- Error codes → Task 1 ✅
- Auth dependency → Task 4 ✅
- CSRF dependency → Task 5 ✅
- Router registration → Task 7 ✅
- Tests → Task 8 ✅

**2. Placeholder scan:** No TBD/TODO found. All code blocks are complete.

**3. Type consistency:**
- `DashboardSession` imported from `app.models.dashboard_session` everywhere ✅
- `UserRole` imported from `app.models.user` ✅
- `ErrorCode` constants match protocol/constants.py additions ✅
- `DomainException` used consistently ✅
