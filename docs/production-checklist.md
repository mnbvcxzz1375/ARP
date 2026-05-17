# Production Checklist

Use this checklist before running AgentNet on a VPS.

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

