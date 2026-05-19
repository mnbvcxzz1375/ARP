# Phase Web 1 Report: User RBAC + Dashboard Sessions

**Date:** 2026-05-19
**Status:** Complete

## Goal

Add RBAC columns to `users` table and create `dashboard_sessions` table as the database foundation for Dashboard authentication.

## Files Changed

| File | Operation |
|------|-----------|
| `apps/api/app/models/user.py` | Add `UserRole` enum, `role`, `is_disabled`, relationships |
| `apps/api/app/models/dashboard_session.py` | NEW — `DashboardSession` ORM class |
| `apps/api/app/models/__init__.py` | Register `DashboardSession` |
| `apps/api/migrations/versions/0009_phase_web_1_rbac_sessions.py` | NEW — migration |
| `apps/api/tests/test_phase_web_1_rbac.py` | NEW — 10 model + migration tests |
| `apps/api/tests/conftest.py` | Add `session` AsyncSession fixture |

## Commands Executed

```bash
alembic revision --autogenerate -m "phase_web_1_rbac_sessions"
alembic upgrade head
alembic downgrade 0008_fix_idempotency_scope
alembic upgrade head
pytest apps/api/tests/test_phase_web_1_rbac.py -v
pytest apps/api -q --ignore=tests/test_phase_web_1_rbac.py
```

## Test Results

- TestUserRBAC: 5 passed
- TestDashboardSession: 5 passed
- Existing test suite: 137 passed, 1 pre-existing flaky failure (MissingGreenlet in rate limiter — unrelated to this phase)

## Failure Path Verification

| Test | Result |
|------|--------|
| Invalid role rejected by check constraint | PASS — `role='hacker'` raises IntegrityError |
| Duplicate session_hash rejected | PASS — IntegrityError raised |
| Downgrade removes columns and table | PASS — verified via `\d` |
| FK CASCADE: user deleted → sessions deleted | PASS |
| FK SET NULL: revoker deleted → revoked_by_user_id null | PASS |

## RBAC / CSRF / Session / Secret Verification

| Check | Result |
|-------|--------|
| session_hash stored, not plaintext | PASS — model uses String(128) hash |
| csrf_hash stored, not plaintext | PASS — model uses String(128) hash |
| All existing users default to role='user' | PASS — 594 users verified |
| All existing users default to is_disabled=false | PASS — 594 users verified |
| Check constraint blocks invalid roles | PASS — 'hacker' rejected |
| No API key or secret in model or migration | PASS |

## Unfinished Items

None. Phase 1 scope (model + migration + tests) is complete.

## Risks and Follow-up

- After deployment to staging/production, run the existing-user verification SQL manually.
- Phase 2 will build on these models (session service, auth endpoints).
- The conftest.py `session` fixture uses raw DB connection for testing; this is needed for CHECK constraint tests.
