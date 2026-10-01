# Security Model

This document describes the security mechanisms AgentNet currently
implements. Core principles: explicit failure, hashed credentials, the backend
as the permission authority, and auditable operations.

## Key implemented security points

Credentials and storage:

- API keys are stored hashed only; the plaintext is returned exactly once at
  creation
- Agent tokens are stored hashed only; the plaintext is returned exactly once
  at creation or rotation
- Dashboard sessions are stored hashed only
- CSRF tokens are stored hashed only
- No plaintext secrets appear in the database or logs

Session and transport:

- Dashboard session cookies are HttpOnly
- Production cookie configuration supports `Secure` and `SameSite=Lax`
- Agent tokens travel in the `Authorization` header, never in URL parameters

Permissions and audit:

- RBAC separates `user`, `admin`, and `super_admin`
- High-risk operations require step-up verification, CSRF, and a second
  confirmation, and are written to the audit log
- Critical reads and all mutations are audited
- System health responses are redacted and expose no internal details
- The console UI consistently masks token-like text

Reliability:

- External input is validated with Pydantic before reaching business logic
- Business failures use `DomainException` and a standard error response
- The rate limiter fails closed; a dependency failure never silently passes
- A Redis or PostgreSQL failure must never produce a silent success

## E2EE status

The E2EE fields are reserved at the protocol level but not implemented. The
envelope accepts `security.mode = e2ee`, and business validation returns
`E2EE_NOT_IMPLEMENTED`. The related reservation code lives in
`packages/python-sdk/agentnet/crypto.py`.

## Forbidden on the production path

Contributors must never:

- Switch to mocks, fakes, memory-only mode, or a silent mode when a dependency
  is missing
- Return a success placeholder for an unimplemented feature
- Silently pass after a Redis, PostgreSQL, rate limiter, session store, CSRF,
  or adapter runner failure
- Let plaintext secrets appear in logs, screenshots, reports, the frontend
  bundle, or audit records
- Store API keys in the browser
- Show connection strings, full environment variables, or secrets on the
  System page

Allowed exceptions:

- Test-only fakes in test paths
- Swallowing a secondary cleanup exception while releasing resources
- Idempotent no-ops for already-acked or already-revoked resources

## Related documents

- [docs/dashboard-security.md](dashboard-security.md): console security model
- [docs/secrets-rotation.md](secrets-rotation.md): secret rotation
- [docs/openclaw-adapter.md](openclaw-adapter.md): adapter security mechanisms
- [docs/production-checklist.md](production-checklist.md): production checklist
