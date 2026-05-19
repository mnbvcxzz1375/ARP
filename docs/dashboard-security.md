# AgentNet Dashboard Security Guide

## Authentication

- Login: `username + API key` → HttpOnly session cookie
- Session cookie: `SameSite=Lax`, `Secure=true` (production), `HttpOnly=true`
- CSRF cookie: `SameSite=Lax`, `Secure=true` (production), `HttpOnly=false` (needed for JS)
- Session token stored as SHA-256 hash only
- CSRF token stored as SHA-256 hash only

## CSRF Protection

All POST/PUT/PATCH/DELETE to `/v1/dashboard/*` require `X-CSRF-Token` header.
The frontend reads the CSRF cookie and sets it via Axios interceptor.

## Secret Handling

| Secret | Stored | Returned |
|--------|--------|----------|
| API key | SHA-256 hash | Only once on creation |
| Agent token | SHA-256 hash | Only once on creation/rotation |
| Session token | SHA-256 hash | Only via Set-Cookie |
| CSRF token | SHA-256 hash | Only via Set-Cookie |

## Data Isolation

- Users can only see their own agents, tasks, approvals, connections, and API keys.
- Admins can read global data but cannot mutate without proper permissions.
- API key ownership enforced at the service layer.

## Security Headers (Production nginx)

| Header | Value |
|--------|-------|
| X-Frame-Options | DENY |
| X-Content-Type-Options | nosniff |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | camera=(), microphone=(), geolocation=() |

## Production Checklist

- [ ] Change all default passwords in `.env.production`
- [ ] Enable TLS with valid certificate
- [ ] Set `SESSION_SECURE_COOKIE=true`
- [ ] Verify CSRF protection works
- [ ] Test admin isolation (regular user cannot access admin endpoints)
- [ ] Verify system health page shows no secrets
