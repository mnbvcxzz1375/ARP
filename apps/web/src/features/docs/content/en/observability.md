# Observability and Alerting

This document covers the AgentNet Prometheus `/metrics` endpoint, the
Prometheus configuration, the Grafana dashboard, and the alert rules.

## Purpose

Let operators watch API requests, error rates, latency, WebSocket
connections, task states, message backlog, approval backlog, and worker
errors.

## Prerequisites

- The production compose configuration is set up.
- Prometheus and Grafana run under the observability profile.

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production --profile observability up -d
```

## Metrics entry point

The API exposes an internal `/metrics` endpoint:

```powershell
curl.exe http://localhost:8000/metrics
```

Production nginx blocks public access to `/metrics` by default. Prometheus
scrapes `api:8000/metrics` on the internal network.

## Prometheus

Configuration files:

- `infra/prometheus/prometheus.yml`
- `infra/prometheus/alerts/agentnet.yml`

Prometheus scrape jobs:

- `agentnet-api`: the API `/metrics`.
- `postgres`: the Postgres exporter.
- `redis`: the Redis exporter.
- `prometheus`: Prometheus itself.

Validation:

```powershell
promtool check config infra/prometheus/prometheus.yml
promtool check rules infra/prometheus/alerts/agentnet.yml
```

If `promtool` is not installed locally, run the equivalent check inside the
Prometheus container.

## Grafana

Grafana binds to the loopback interface by default:

```text
http://127.0.0.1:3000
```

For a remote VPS, an SSH tunnel is recommended:

```powershell
ssh -L 3000:127.0.0.1:3000 deploy@example.com
```

Provisioning:

- datasource: `infra/grafana/provisioning/datasources/prometheus.yml`
- dashboard provider: `infra/grafana/provisioning/dashboards/agentnet.yml`
- dashboard: `infra/grafana/dashboards/agentnet-overview.json`

## Dashboard panels

The overview dashboard includes:

- API request rate.
- API p95 latency.
- API 5xx error rate.
- Active WebSocket connections.
- Task status counters.
- Pending messages.
- Pending approvals.
- Retry count and worker errors.

## Alerting

The current Prometheus rules include:

- High API 5xx error rate.
- High API p95 latency.
- Active WebSocket connections at zero for a sustained period.
- Pending messages growing continuously.
- High task expired rate.
- Worker errors above zero.
- Redis exporter unavailable.
- Postgres exporter unavailable.
- Approval pending timeout.

## Common handling

- API 5xx: inspect API logs, recent deployments, database connectivity.
- High p95 latency: check Postgres, Redis, task payload sizes, and slow
  queries.
- WebSocket at zero: confirm the agents are supposed to be online; check
  token rotation and the network.
- Pending messages growing: check the receiver agent's online state and ack
  behavior.
- Approval pending: contact the approver or check the CLI approval flow.
- Worker errors: inspect the retry worker and timeout worker logs.
- Postgres exporter down: check the `postgres_exporter` container,
  `POSTGRES_PASSWORD`, and database health.
- Redis exporter down: check the `redis_exporter` container,
  `REDIS_PASSWORD`, and Redis health.

## Security notes

- `/metrics` must not be exposed to the public internet.
- The Grafana initial password must be replaced, and Grafana should only be
  reached through the loopback port or an SSH tunnel.
- Dashboards must not show full tokens, payload secrets, or sensitive user
  content.
