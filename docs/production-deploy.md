# Production Deploy

This guide describes the Phase 11.2 single-node Docker Compose VPS deployment template.

## Purpose

The production template runs AgentNet behind nginx with private Postgres and Redis services. It is intended for a small production validation or private beta, not large multi-region deployment.

## Prerequisites

- A Linux VPS with Docker Engine and Docker Compose.
- A domain pointing to the VPS.
- SSH access to the VPS.
- Python is not required on the host if you run only Docker Compose.

## Files

```text
infra/docker-compose.prod.yml
infra/.env.production.example
infra/nginx/agentnet.conf
```

## First Deploy

Copy the environment template:

```powershell
Copy-Item infra/.env.production.example infra/.env.production
```

Edit `infra/.env.production` and replace every `CHANGE_ME` value.

Validate the compose file:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production config
```

Build and start:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up --build -d
```

Run migrations:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head
```

Check health:

```powershell
curl http://localhost/healthz
```

Expected response:

```json
{"status":"ok"}
```

## Stop

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production down
```

This keeps named volumes by default. Do not use `--volumes` unless you intentionally want to delete persisted data.

## Upgrade

Pull or copy the new code, then run:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production build api
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up -d
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head
curl http://localhost/healthz
```

## Rollback

Rollback requires a known-good code version and a database state compatible with that version.

Recommended order:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production down
git checkout <known-good-version>
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up --build -d
curl http://localhost/healthz
```

If the failed release included database migrations, follow `docs/backup-restore.md` once Phase 11.5 is implemented.

## Logs

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f api
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f nginx
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f postgres
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f redis
```

## Observability Profile

Prometheus and Grafana are present behind the `observability` profile. Phase 11.7 wires `/metrics`, dashboards, and alerts.

Start the profile:

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production --profile observability up -d
```

Grafana binds to `127.0.0.1:3000` by default. Access it through SSH tunneling:

```powershell
ssh -L 3000:127.0.0.1:3000 user@example.com
```

Then open:

```text
http://localhost:3000
```

## Security Notes

- Do not commit `infra/.env.production`.
- Do not expose Postgres or Redis ports publicly.
- Do not expose `/metrics` publicly.
- Use strong random values for all passwords.
- Put TLS in front of nginx before public use.

