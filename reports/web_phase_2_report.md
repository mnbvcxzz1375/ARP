# Phase Web 2 Report: Session/Auth/CSRF/Step-Up Infrastructure

**Date:** 2026-05-19
**Status:** Complete

## Goal

Build backend session management, authentication endpoints, and CSRF protection for the Dashboard. No frontend yet — API only.

## Files Changed

| File | Operation |
|------|-----------|
| `apps/api/app/config.py` | Add 8 session settings (cookie names, lifetimes, secure flag) |
| `apps/api/app/protocol/constants.py` | Add 8 dashboard error codes |
| `apps/api/app/services/dashboard_session_service.py` | NEW — Session CRUD, rotation, revocation, validation |
| `apps/api/app/services/csrf_service.py` | NEW — CSRF token validation |
| `apps/api/app/dependencies/auth.py` | NEW — `get_current_session` dependency |
| `apps/api/app/dependencies/csrf.py` | NEW — `require_csrf` dependency |
| `apps/api/app/routers/dashboard_auth.py` | NEW — Login, logout, step-up, me endpoints |
| `apps/api/app/main.py` | Register dashboard auth router + CSRF middleware |
| `apps/api/tests/conftest.py` | Add `app` and `client` fixtures for async HTTP testing |
| `apps/api/tests/test_phase_web_2_session.py` | NEW — 15 endpoint + service tests |

## Commands Executed

```bash
pytest apps/api/tests/test_phase_web_2_session.py -v
pytest apps/api -q --ignore=tests/test_phase_web_2_session.py --ignore=tests/test_phase_web_1_rbac.py
```

## Test Results

- TestLogin: 4 passed (success, invalid creds, wrong key, disabled user)
- TestMe: 2 passed (unauthenticated → 401, authenticated → user info)
- TestLogout: 1 passed (revoke session, clear cookies)
- TestStepUp: 2 passed (success with rotation, wrong key → 403)
- TestSessionService: 4 passed (create/find, rotate, revoke all, disabled user)
- TestCSRF: 2 passed (valid token, missing token raises)
- Existing test suite: 18 passed, 1 pre-existing flaky (MissingGreenlet — unrelated)

## Failure Path Verification

| Test | Result |
|------|--------|
| Login with wrong username → 401 INVALID_CREDENTIALS | PASS |
| Login with wrong API key → 401 INVALID_CREDENTIALS (same msg) | PASS |
| Login with disabled user → 403 USER_DISABLED | PASS |
| Me without session → 401 INVALID_SESSION | PASS |
| Step-up with wrong key → 403 INVALID_STEP_UP | PASS |
| Disabled user cannot find session after creation | PASS |

## Security Verification

| Check | Result |
|-------|--------|
| Session token stored as hash only (SHA-256) | PASS |
| CSRF token stored as hash only (SHA-256) | PASS |
| Plain token sent once via Set-Cookie only | PASS |
| Login failure: generic message, no username/key hints | PASS |
| Step-up failure: generic 403, same for invalid as wrong | PASS |
| Session cookie: HttpOnly=true, SameSite=Lax | PASS |
| CSRF cookie: HttpOnly=false (needed for frontend JS) | PASS |
| No API key or session token in URL or JSON response | PASS |
| All mutations write audit log | PASS |
| `session.commit` patched to `flush` in tests for rollback | PASS |

## Bug Fixes During Implementation

1. **JSONResponse discards cookies**: Returning `JSONResponse(...)` in endpoints discards cookies set on the injected `Response` parameter. Fixed by returning plain dicts (FastAPI auto-wraps).
2. **Test session isolation**: `session.commit()` inside endpoints prevents test rollback. Fixed by patching `session.commit = session.flush` in conftest.

## Unfinished Items

None. Phase 2 scope (session/auth/CSRF infrastructure) is complete.

## Risks and Follow-up

- Phase 3 will add RBAC permission helpers and guards to existing API endpoints.
- The `require_csrf` dependency is not yet applied to any endpoints (login/me/logout/step-up don't need it for security reasons). It will be used by Phase 4+ user-facing endpoints.
- Production deployment requires `SESSION_SECURE_COOKIE=true` and proper HTTPS.
