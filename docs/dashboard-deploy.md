# AgentNet Dashboard Deployment Guide

## Overview

The AgentNet Dashboard consists of:
- **Frontend**: React + TypeScript SPA (Vite build), served via nginx
- **Backend**: FastAPI (Python) REST API
- **Infrastructure**: PostgreSQL + Redis + optional observability stack

## Development

### Prerequisites
```bash
node --version  # >= 22
python3 --version  # >= 3.11
docker compose version  # >= 2.24
```

### Start Dev Environment

```bash
# Start API + DB + Cache
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up

# Start frontend separately (for hot-reload)
cd apps/web && npm install && npm run dev

# Or start everything together:
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up --build
```

- Frontend: http://localhost:5173 (proxies API to localhost:8000)
- API: http://localhost:8000

## Production Build

### Build Frontend
```bash
cd apps/web && npm ci && npm run build
# Output: apps/web/dist/
```

### Docker Production Build
```bash
docker compose -f infra/docker-compose.prod.yml up -d api web nginx
# Or with observability:
docker compose -f infra/docker-compose.prod.yml --profile observability up -d
```

### Nginx Configuration

The production nginx config serves the SPA with:
- SPA fallback for `/app/*`, `/admin/*`, `/login`
- API proxy for `/v1/*` and `/healthz`
- Security headers (CSP, X-Frame-Options, etc.)
- Long-lived cache headers for `/assets/*`

Customize `infra/nginx/agentnet.conf` for:
- SSL/TLS certificates (production)
- Custom domain names
- Rate limiting
- Logging

### Environment Variables

| Variable | Dev Default | Prod Required |
|----------|-------------|---------------|
| `VITE_AGENTNET_API_BASE` | (proxy) | `https://your-domain.com` |
| `POSTGRES_PASSWORD` | `agentnet` | CHANGE_ME |
| `REDIS_PASSWORD` | (none) | CHANGE_ME |

## Full Stack Production

### docker-compose.prod.yml

The production compose includes:
- API service (FastAPI, uvicorn)
- Web service (nginx + built SPA)
- PostgreSQL 16
- Redis 7
- nginx reverse proxy
- Optional: Prometheus + Grafana (profile: observability)

```bash
# Copy and edit production env
cp infra/.env.production.example infra/.env.production
# Edit passwords in infra/.env.production

# Deploy
docker compose -f infra/docker-compose.prod.yml up -d

# Check health
curl https://your-domain.com/healthz
```

### Manual Deployment (without Docker)
```bash
# Build frontend
cd apps/web && npm ci && npm run build

# Serve with nginx:
# 1. Copy apps/web/dist/ to /var/www/agentnet/
# 2. Copy infra/nginx/agentnet.conf to /etc/nginx/sites-enabled/
# 3. Restart nginx
```

## Security

- Session cookies: HttpOnly + SameSite=Lax + Secure (production)
- CSRF: separate non-HttpOnly cookie + X-CSRF-Token header
- API keys returned only once (on creation)
- Agent tokens returned only once (on creation/rotation)
- SecretMaskedText component masks secrets in the UI
- Admin actions require step-up authentication for high-risk operations
- System health page exposes no secrets

## Monitoring

- API health: `/healthz`
- Prometheus metrics: `/metrics` (internal only)
- Grafana dashboards: included in infra/grafana/
- Frontend: no built-in monitoring (browser dev tools)
