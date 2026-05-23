# Production Checklist

Use this checklist before running AgentNet on a VPS.

For the stricter production closeout gates, Web UI decision, and final acceptance standard, see:

- [Production Closeout Plan](production-closeout.md)

## Environment

- [ ] Docker Engine is installed.
- [ ] Docker Compose works.
- [ ] Domain DNS points to the server.
- [ ] Firewall allows only SSH, HTTP, and HTTPS as needed.
- [ ] `infra/.env.production` exists and is not committed.
- [ ] Every `CHANGE_ME` value was replaced.

## Compose Validation

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production config
```

- [ ] Compose config passes.
- [ ] API has no public port mapping.
- [ ] Postgres has no public port mapping.
- [ ] Redis has no public port mapping.
- [ ] nginx is the only public HTTP entrypoint.

## Database

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic current
```

- [ ] Migrations reach head.
- [ ] `alembic current` reports the expected revision.

## Health

```powershell
curl http://localhost/healthz
```

- [ ] Health endpoint returns `{"status":"ok"}`.
- [ ] API logs do not contain secret values.
- [ ] nginx logs show successful proxying.

## Tokens and Secrets

- [ ] API keys are not stored in code or shell history.
- [ ] Agent tokens are not stored in code or shell history.
- [ ] Database password is unique for this deployment.
- [ ] Redis password is unique for this deployment.
- [ ] Grafana admin password is unique for this deployment.

## Rollback Readiness

- [ ] Current code version is recorded.
- [ ] Current migration revision is recorded.
- [ ] Backup plan is understood.
- [ ] Restore plan is understood.

## Observability

- [ ] Observability profile is disabled until Phase 11.7 is complete, or started only for internal testing.
- [ ] Grafana is not exposed publicly without TLS and authentication.
- [ ] `/metrics` is not public.

## Dashboard Security

- [ ] Dashboard session cookie is HttpOnly, SameSite=Lax, Secure=true
- [ ] Dashboard CSRF protection is enabled
- [ ] Dashboard admin pages require admin or super_admin role
- [ ] Dashboard admin actions that are high-risk require step-up
- [ ] Dashboard System Health page does not expose DATABASE_URL, REDIS_URL, tokens, or passwords
- [ ] Dashboard user cannot access admin endpoints (403)
- [ ] SecretMaskedText component masks secrets in UI
- [ ] API key only returned once (on creation)
- [ ] Agent token only returned once (on creation/rotation)

## Dashboard Performance

- [ ] Overview pages use polling with appropriate intervals (user 15s, admin 30s, system health 10s)
- [ ] All lists are paginated (default 50, max 200)
- [ ] TanStack Query retry is configured (default 1 retry)

## Routing Runtime Closeout

- [ ] Egress Gateway is enforced by adapters, not only available as a service.
- [ ] Network-level egress bypass is blocked or explicitly documented for private pilot scope.
- [ ] Dedicated Channel CRUD/API or approved operational workflow exists.
- [ ] Route decisions and delivery timelines are visible to operators.
- [ ] SLA violations, circuit breaker state, and failover events are visible to operators.
- [ ] Redis/Postgres/API/worker/egress/relay failure drills are recorded.
- [ ] Final production acceptance report is created under `reports/`.
