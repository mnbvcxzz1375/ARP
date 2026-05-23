# Phase 2 Design: Session/Auth/CSRF/Step-Up Infrastructure

**Date**: 2026-05-19
**Status**: Approved
**Scope**: AgentNet Enterprise Dashboard — Phase 2 of 13
**Predecessor**: 0009_phase_web_1_rbac_sessions (Phase 1)

## Summary

Build the backend session management, authentication endpoints, and CSRF protection infrastructure for the Dashboard. No frontend pages yet — only API endpoints and service layer.

Delivers: session creation/verification/rotation, login/logout/step-up/me endpoints, CSRF token validation, cookie-based auth, and config settings.

## Authentication Flow

```
username + API key -> POST /v1/dashboard/auth/login -> HttpOnly session cookie + CSRF cookie
```

Session is stored as hash only. Plain text token sent once via Set-Cookie, never stored or returned again.

## API Endpoints

### POST /v1/dashboard/auth/login

Request body:
```json
{"username": "...", "api_key": "..."}
```

Response (200):
```json
{"session_token": "...", "csrf_token": "...", "expires_at": "..."}
```

- Sets `session_token` as HttpOnly cookie.
- Sets `csrf_token` as non-HttpOnly cookie.
- Creates `DashboardSession` with session hash, csrf hash, role-based lifetime.
- Writes audit: `dashboard.login.success`.

Failure responses:
- 401 `INVALID_CREDENTIALS` — generic, no hint about username/key existence.
- 403 `USER_DISABLED` — user found but `is_disabled=true`.

### POST /v1/dashboard/auth/logout

Requires authenticated session cookie.

- Revokes current session with reason `logout`.
- Clears cookies.
- Writes audit: `dashboard.logout`.

### POST /v1/dashboard/auth/step-up

Request body:
```json
{"api_key": "..."}
```

Requires authenticated session cookie.

- Verifies API key matches current user.
- Sets `step_up_until = now + 10 minutes`.
- Rotates session (new token, new hash, old revoked with `session_rotated`).
- Writes audit: `dashboard.step_up.success` or `dashboard.step_up.failed`.
- Sets new session cookie.

Failure: 403 `INVALID_STEP_UP` — generic, no hint.

### GET /v1/dashboard/auth/me

Requires authenticated session cookie.

Response (200):
```json
{
  "user_id": "...",
  "username": "...",
  "role": "...",
  "permissions": ["...", "..."],
  "csrf_required": true,
  "session_expires_at": "...",
  "step_up_until": "..."
}
```

- Updates `last_seen_at`.

## Session Lifecycle

| Role        | Absolute Lifetime | Idle Timeout |
|-------------|------------------:|-------------:|
| user        | 30 days           | 24h          |
| admin       | 7 days            | 2h           |
| super_admin | 7 days            | 2h           |

Rotation triggers: login, step-up success, role change, high-risk mutation.
Revoke triggers: user disabled, API key force-revoke, explicit logout.

## Cookie Policy

Session cookie: `HttpOnly=true, SameSite=Lax, Secure=true (production), Path=/`
CSRF cookie: `HttpOnly=false, SameSite=Lax, Secure=true (production), Path=/`

Cookie names: `agentnet_session`, `agentnet_csrf`

## CSRF Protection

All POST/PUT/PATCH/DELETE to `/v1/dashboard/*` require `X-CSRF-Token` header matching the current session's CSRF hash.

GET/HEAD/OPTIONS exempt.

Error codes: `CSRF_TOKEN_MISSING`, `CSRF_TOKEN_INVALID`.

## File Structure

| File | Operation | Responsibility |
|------|-----------|---------------|
| `apps/api/app/config.py` | Modify | Add session settings (lifetimes, cookie names) |
| `apps/api/app/services/session_service.py` | Create | Session CRUD, rotation, revocation, validation |
| `apps/api/app/services/csrf_service.py` | Create | CSRF token generation and validation |
| `apps/api/app/routers/dashboard_auth.py` | Create | Login, logout, step-up, me endpoints |
| `apps/api/app/dependencies/auth.py` | Create | `get_current_session` dependency |
| `apps/api/app/dependencies/csrf.py` | Create | `require_csrf` dependency |
| `apps/api/app/main.py` | Modify | Register dashboard auth router |
| `apps/api/tests/test_phase_web_2_session.py` | Create | Auth/session/CSRF tests |
| `reports/web_phase_2_report.md` | Create | Phase report |

## Security Requirements

- Never log or return plain session token after Set-Cookie.
- Never return plain CSRF token in JSON response (only via Set-Cookie).
- Login failure: generic message, no username/key existence hints.
- Step-up failure: generic 403, same for invalid key as for wrong key.
- Session cookie: `Secure=true` in production (config-driven).
- All admin/session mutations write audit log.
- No API key or session token in URL path or query string.

## Assumptions

- Phase 1 migration (dashboard_sessions table) is already applied.
- `User.role` enum (`user`/`admin`/`super_admin`) is available.
- Existing `/v1/auth` endpoints remain unchanged (API-key-only auth).
- This phase does NOT add RBAC guards to existing API endpoints (Phase 3).
