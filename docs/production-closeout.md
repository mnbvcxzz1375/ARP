# AgentNet Production Closeout Plan

This document defines the final production closeout work after the current development pass. It is intentionally stricter than a feature checklist: an item is accepted only when the code path, configuration, tests, documentation, and operational evidence all line up.

Current verified backend baseline:

```text
python -m pytest -q
440 passed, 31 warnings
```

This means the backend test suite is green in a clean migrated test database. It does not by itself mean the platform is ready for public production traffic.

## Release Position

The current codebase is suitable for:

- Controlled internal testing.
- Staging validation.
- Private pilot deployments with known users and supervised operations.
- Demonstrating AgentNet Routing Runtime, Dashboard, Egress Gateway, Dedicated Channel core service behavior, SLA metrics, and business continuity primitives.

The current codebase is not yet suitable for:

- Unsupervised public SaaS launch.
- Enterprise production with strict compliance requirements.
- Environments where agents can bypass the platform network controls.
- Deployments that require formal incident response, alert routing, backup recovery proof, and multi-hour failure drills.

## First Principles For Closeout

1. Production readiness is an operational property, not only a test result.
2. A feature is complete only when the real production path uses it.
3. No dependency failure may return a fake success.
4. Security policy must be enforced before route scoring, performance optimization, or convenience.
5. Dashboard pages must expose operational truth without leaking secrets.
6. Acceptance requires both happy path and failure path evidence.
7. Every production change must have a rollback path.

## Required Production Closeout Items

### P0. Egress Enforcement

Status: Required before public production.

Current state:

- `egress_service.py` implements domain allowlist, env-based secret injection, high-risk approval, Redis rate limiting, GET cache, cost tracking, egress logs, and fail-closed Redis error handling.
- The egress service is not yet guaranteed as the only way all adapters make external HTTP/API calls.
- Network-level enforcement is not yet proven.

Required work:

- Route OpenClaw and future adapters through `proxy_external_request()` for external HTTP/API/model/GitHub/deployment/MCP calls.
- Block direct adapter access to external secrets.
- Define and test an adapter contract: external access must either use Egress Gateway or fail.
- Add network-level controls in production where possible, such as egress proxy, firewall, container network policy, or service mesh policy.
- Add tests proving that an adapter cannot bypass configured egress policy in production mode.

Acceptance evidence:

- Adapter tests for allowed domain, denied domain, missing secret, agent-provided Authorization header, rate limit, cache hit, and high-risk approval.
- A staging run where a denied external domain fails closed and creates audit/egress log evidence.
- Production config document showing how direct outbound traffic is restricted.

### P1. Dedicated Channel Management API

Status: Required for enterprise production if VPN, P2P, Private Link, or Direct Connect is offered.

Current state:

- Dedicated Channel models, service logic, health check records, Path Optimizer integration, and tests exist.
- No dedicated REST CRUD schema/router exists for channel lifecycle management.
- Channel creation currently depends on direct service/database access or future admin tooling.

Required work:

- Add `apps/api/app/schemas/dedicated_channel.py`.
- Add `apps/api/app/routers/dedicated_channel.py` or admin-scoped routes.
- Support create, list, detail, update, enable/disable, health check ingest, and revoke/delete.
- Enforce RBAC:
  - `admin`: read channels and health.
  - `super_admin`: create/update/disable/delete channels.
  - Step-up required for enable, disable, delete, and endpoint/secret-affecting changes.
- Audit every read of sensitive channel configuration metadata and every mutation.
- Never expose private keys, tokens, tunnel credentials, or complete connection secrets.

Acceptance evidence:

- API tests for role boundaries, step-up, mutation audit, and secret masking.
- Dedicated channel failure path tests: missing health check, unhealthy report, DB query error, disabled channel.
- OpenAPI regenerated and reviewed.

### P2. Web UI Updates

Status: Required for enterprise operations, not required for a private developer-only pilot.

The current Web Dashboard already covers user/admin basics. For production enterprise operation, it should be updated because several new Routing Runtime features are only partially visible through the UI.

Required UI updates:

- Admin Network Overview:
  - Relay health by type: central, personal edge, local edge, regional, egress, dedicated.
  - Queue depth, current load, latency, success rate, fallback count.
  - Clear degraded/down indicators.
- Route Decisions:
  - Task route selected.
  - Candidate routes.
  - Rejection reasons.
  - Applied route policy.
  - Route lease ID and expiry.
  - Fallback reason when present.
- Task Detail:
  - Delivery timeline: queued, route_selected, delivering, delivered, acknowledged, delivery_failed, expired.
  - Execution timeline: created, received, accepted, running, progress, waiting_input, succeeded, failed, expired.
  - Route decision summary.
- Egress Logs:
  - Gateway, domain, request type, status code, latency, cost estimate, approval ID.
  - Filters by gateway, agent, task, domain, status.
  - No request body secrets or Authorization headers.
- Dedicated Channels:
  - Channel type, source/target agent, status, latest health check, latency, packet loss, bandwidth.
  - Super admin controls for enable/disable/revoke with step-up.
- SLA and Continuity:
  - SLA targets.
  - SLA violations.
  - Circuit breaker state.
  - Failover configs and events.
  - Manual failover/rollback controls behind super_admin plus step-up.
- System Page:
  - Keep summary-only behavior.
  - Do not display connection strings, environment variables, raw secrets, private keys, full tokens, or full payloads.

Not required for first enterprise closeout:

- Marketing landing page.
- Full visual topology graph editor.
- Real-time animated network map.
- Multi-tenant billing dashboard.

UI acceptance evidence:

- Component tests for every new page.
- API client tests for route/egress/SLA/continuity endpoints.
- Browser smoke test covering login, admin navigation, route decision detail, egress logs, and SLA page.
- Screenshots stored under `reports/` for the final release candidate.
- Manual review confirming no secret values are visible in the UI.

### P3. Observability And Alerting

Status: Required before production.

Current state:

- Prometheus/Grafana templates exist.
- Route metrics, SLA targets, SLA violations, circuit breaker, and failover models/services exist.
- Alert routing and production drill evidence are not complete.

Required work:

- Add or verify Prometheus alerts for:
  - API unavailable.
  - PostgreSQL unavailable.
  - Redis unavailable.
  - WebSocket disconnect spike.
  - Egress failure spike.
  - Route fallback spike.
  - Ack timeout spike.
  - Processing timeout spike.
  - SLA critical violation.
  - Circuit breaker open.
  - Failover triggered.
- Define alert destinations:
  - Email, webhook, PagerDuty, DingTalk, Slack, or another operator-owned channel.
- Add dashboard panels:
  - API latency and errors.
  - WebSocket online agents.
  - Task status distribution.
  - Message delivery status distribution.
  - Route latency and success rate.
  - Egress status and cost.
  - SLA violations.
  - Failover events.

Acceptance evidence:

- `promtool` validates alert rules.
- Grafana dashboard imports successfully.
- At least one synthetic alert is triggered in staging and acknowledged.
- Alert payload contains enough context but no secrets.

### P4. Fault Injection And Business Continuity Drills

Status: Required before production.

Required drills:

- Redis unavailable:
  - API must not pretend agents are online.
  - Rate limiter/session/egress cache failures fail closed where required.
- PostgreSQL unavailable:
  - Task creation must fail clearly.
  - No fake task ID or success response.
- API restart:
  - WebSocket reconnect and session resume must recover unacked pending messages.
- Worker restart:
  - Retry, timeout, SLA, and continuity workers resume from persisted state.
- Relay degraded/down:
  - Route selection respects policy.
  - Reroute happens only when policy allows it.
  - Denied fallback fails closed with route decision/audit evidence.
- Egress gateway disabled/down:
  - External calls fail or wait for approval; agents do not bypass gateway.
- Dedicated channel down:
  - Channel unavailable is recorded.
  - Policy controls fail or reroute behavior.

Acceptance evidence:

- A drill report under `reports/production_drill_<date>.md`.
- Commands executed.
- Expected result versus actual result.
- Logs or screenshots showing audit, route decision, metric, and alert evidence.
- Rollback and recovery notes.

### P5. Backup, Restore, And Migration Readiness

Status: Required before production.

Required work:

- Run a real backup on staging-like data.
- Restore it into a clean database.
- Verify application health after restore.
- Record migration head before and after deployment.
- Confirm downgrade or restore strategy for failed migration.

Acceptance evidence:

- Backup file and checksum created.
- Restore command executed successfully.
- `alembic current` returns expected revision.
- Smoke tests pass after restore.

### P6. Secret Management And Rotation

Status: Required before production.

Required work:

- Do not store real secrets in Git.
- Keep `.env.production` out of version control.
- Replace all `CHANGE_ME` values.
- Define owner and rotation interval for:
  - PostgreSQL password.
  - Redis password.
  - Dashboard session secret or signing material if introduced.
  - API keys.
  - Agent tokens.
  - Egress gateway secrets.
  - TLS certificates.
- Move beyond `env:` egress secret refs for enterprise production, or document why env-only is acceptable for the first private pilot.

Acceptance evidence:

- Secret inventory completed.
- Rotation runbook tested for at least one API key, one Agent token, and one infrastructure secret.
- Logs verified to contain no secret values.

### P7. Production Deployment Verification

Status: Required before production.

Required work:

- Deploy with production Docker Compose or equivalent.
- Enable HTTPS for `andrewhyc.top`.
- Verify WSS works through nginx.
- Verify secure cookies:
  - `SESSION_SECURE_COOKIE=true`.
  - Session cookie is HttpOnly.
  - CSRF behavior works.
- Verify API is not directly exposed except through intended public entrypoint.
- Verify PostgreSQL and Redis are not publicly exposed.

Acceptance evidence:

- `curl https://andrewhyc.top/healthz` returns healthy status.
- Browser login works on HTTPS.
- WebSocket connection succeeds over WSS.
- Dashboard loads production build, not Vite dev server.
- nginx access/error logs show expected proxy behavior.

## Web UI Decision

Does Web UI need to be updated?

Yes for enterprise production. No for a small private pilot if operators are comfortable using API/SQL for advanced routing operations.

Required for public or enterprise production:

- Route decision visibility.
- Delivery timeline on task detail.
- Network/relay health page.
- Egress log page.
- Dedicated channel management page.
- SLA/continuity page.
- Super admin step-up for dangerous actions.

Can be deferred for private pilot:

- Dedicated channel CRUD UI if channels are manually provisioned.
- SLA visual charts if operators use Grafana.
- Full topology visualization.

Do not defer:

- Secret masking.
- RBAC.
- Step-up on high-risk admin actions.
- System page no-secret rule.
- Clear task delivery status.

## Production Acceptance Standard

The release is production-acceptable only when all mandatory criteria below pass.

### Code And Tests

- Backend full test suite passes from a clean migrated database.
- Web unit/component tests pass.
- Web production build passes.
- OpenAPI export is regenerated and checked for drift.
- No production code path returns success for missing dependency or unimplemented feature.
- No real secret appears in repo, logs, reports, screenshots, or generated artifacts.

### API And Runtime

- Task creation returns explicit status and delivery state.
- Message delivery events are persisted.
- Ack changes message state to acknowledged.
- Offline queue and session resume recover unacked messages.
- Route decision is persisted for routed tasks.
- Route lease expiry, revocation, max messages, max bytes, and allowed task type restrictions are enforced.
- Policy denial cannot be bypassed by fallback.

### Security

- Dashboard session and CSRF protections work over HTTPS.
- RBAC blocks unauthorized user/admin/super_admin access.
- Step-up is required for high-risk admin actions.
- Agent tokens and API keys are hash-stored and only shown once.
- Egress secrets are not exposed to agents.
- System health page does not leak secrets or full environment values.

### Egress

- Allowed external request succeeds through Egress Gateway.
- Denied domain fails closed.
- Missing egress secret fails closed.
- Agent-provided Authorization header is rejected when gateway-managed secret is configured.
- Egress rate limit throttles with 429.
- Redis failure in egress rate/cache path fails closed with 503.
- High-risk external operation creates approval and does not execute before approval.

### Dedicated Channel

- Dedicated channel is selected only when enabled, authorized, policy-allowed, and healthy.
- Missing or invalid health report marks channel down.
- Dedicated channel DB/query errors fail closed.
- Channel down behavior is explicit: fail or reroute according to policy.
- All mutations are audited.

### Observability

- `/metrics` is protected from public exposure.
- Prometheus scrapes API and infrastructure exporters.
- Grafana dashboard imports.
- Critical alerts are defined and tested.
- SLA violations are queryable.
- Failover events are queryable.

### Operations

- Production deployment can be reproduced from documented commands.
- Backup and restore are tested.
- Rollback path is documented.
- Incident runbook exists for secret leak, database failure, Redis failure, and egress failure.
- At least one staging failure drill is completed and recorded.

## Release Gate

Use this decision table before launch.

| Gate | Required Result | Launch Decision |
|------|-----------------|-----------------|
| Backend tests | Full suite passes from clean DB | Required |
| Web tests/build | Unit tests and production build pass | Required |
| HTTPS/WSS | Real domain works | Required |
| Egress enforcement | Adapter and network enforcement proven | Required for public production |
| Dedicated Channel CRUD | API/UI or documented admin workflow exists | Required for enterprise dedicated channels |
| Observability | Alerts and dashboards tested | Required |
| Backup/restore | Restore drill passed | Required |
| Secret rotation | Runbook tested | Required |
| Failure drills | Redis/Postgres/API/Egress/Relay scenarios recorded | Required |

## Recommended Closeout Order

1. Finish Egress adapter integration and network-level restriction.
2. Add Dedicated Channel schemas/router and admin UI if enterprise channel management is needed.
3. Update Dashboard for route decisions, egress logs, dedicated channels, SLA, and continuity.
4. Regenerate OpenAPI and update API documentation.
5. Run backend, web, browser, and WebSocket E2E tests from clean databases.
6. Deploy staging with production-like TLS and WSS.
7. Run backup/restore and failure drills.
8. Validate observability and alert routing.
9. Produce final `reports/production_acceptance_<date>.md`.
10. Approve production launch only if all required gates pass.

## Final Acceptance Report Template

Create a report at:

```text
reports/production_acceptance_<YYYY-MM-DD>.md
```

Minimum content:

- Commit or build identifier.
- Deployment environment.
- Configuration files used.
- Migration revision.
- Backend test result.
- Web test/build result.
- Browser E2E result.
- WebSocket E2E result.
- OpenAPI drift result.
- Backup/restore evidence.
- Secret scan result.
- Observability validation.
- Failure drill summary.
- Web UI review result.
- Security review result.
- Known risks.
- Go/no-go decision.
