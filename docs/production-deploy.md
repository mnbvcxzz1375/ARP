# Production Deploy -- andrewhyc.top

This guide describes the single-node Docker Compose production deployment for the domain **andrewhyc.top**.

## Architecture

```text
Internet ──┐
            v
    ┌──────────────┐   /v1/*  /healthz  /metrics  /v1/ws    ┌──────────┐
    │  nginx:443   │   /openapi.json  /docs  /redoc        │   api    │
    │  (TLS 1.3)   │ ────────────────────────────────────▶ │  :8000   │
    │              │                                        └──────────┘
    │              │   /login  /app/*  /admin/*  /*          ┌──────────┐
    │ andrewhyc.top│ ────────────────────────────────────▶ │   web    │
    └──────────────┘                                        │  :80     │
            │                                               └──────────┘
            │ 80 (redirect to 443)
            v
     /.well-known/acme-challenge/   (certbot)
```

- **nginx** -- public entry point, TLS termination, route splitting
- **api** -- FastAPI backend (tasks, agents, auth, WebSocket)
- **web** -- nginx serving the React SPA (`Dockerfile.prod` → static files)
- **postgres** -- primary database
- **redis** -- caching, rate limiting, session store

## Prerequisites

- Docker Engine 24+ and Docker Compose 2.24+
- A registered domain **andrewhyc.top** with DNS pointing to your server
- TLS certificate files (see [Certificates](#certificates) below)
- SSH access (Linux VPS) or administrative shell (Windows)

## Files

```text
infra/
├── docker-compose.prod.yml     # Service definitions
├── .env.production.example     # Environment template
└── nginx/
    └── agentnet.conf           # nginx config (TLS + proxy)
```

## Quick Start

### 1. DNS Setup

Create an **A record** for `andrewhyc.top` pointing to your server's public IP:

| Type | Name  | Value        |
|------|-------|-------------|
| A    | @     | <SERVER_IP> |

Verify propagation:

```bash
dig +short andrewhyc.top
# Should return <SERVER_IP>
```

### 2. Prepare Environment

Copy the template and edit all `CHANGE_ME` values:

```bash
cp infra/.env.production.example infra/.env.production
```

```powershell
# Windows
Copy-Item infra/.env.production.example infra/.env.production
```

Edit `infra/.env.production`:

| Variable                  | Required | Description                            |
|---------------------------|----------|----------------------------------------|
| `POSTGRES_PASSWORD`       | CHANGE   | Database password                      |
| `REDIS_PASSWORD`          | CHANGE   | Redis password                         |
| `GRAFANA_ADMIN_PASSWORD`  | CHANGE   | Grafana admin password                 |

Key defaults already set for andrewhyc.top:

| Variable              | Default                |
|-----------------------|------------------------|
| `PUBLIC_BASE_URL`     | `https://andrewhyc.top`|
| `SESSION_SECURE_COOKIE` | `true`               |

### 3. Certificates

The nginx container expects certificates at `/etc/ssl/agentnet/live/andrewhyc.top/fullchain.pem` (and `.key`).

Mount the host certificate directory via `SSL_CERT_DIR`:

#### Option A -- Linux VPS with Let's Encrypt (default)

```bash
# Install certbot and obtain certificates
sudo apt install certbot
sudo certbot certonly --standalone -d andrewhyc.top

# Default path: /etc/letsencrypt/live/andrewhyc.top/
# SSL_CERT_DIR defaults to /etc/letsencrypt -- no .env change needed.
```

#### Option B -- Linux VPS with custom certs

Place your certificate files at `/etc/ssl/agentnet/live/andrewhyc.top/`, or set:

```ini
# infra/.env.production
SSL_CERT_DIR=/custom/cert/path
```

And ensure the files exist at `/custom/cert/path/live/andrewhyc.top/fullchain.pem`.

#### Option C -- Windows Docker Desktop

```ini
# infra/.env.production
SSL_CERT_DIR=E:\SSL
```

Place certificate files at:

```
E:\SSL\live\andrewhyc.top\fullchain.pem
E:\SSL\live\andrewhyc.top\privkey.pem
```

The mount is read-only (`:ro`) for security.

> **Note:** The `E:\SSL` path on Windows must be shared with Docker Desktop.
> Go to Docker Desktop → Settings → Resources → File Sharing and add `E:\SSL`.

##### From a provider's nginx zip

If your certificate provider delivers a zip file (e.g. `25145853_andrewhyc.top_nginx.zip`)
containing `andrewhyc.top.pem` and `andrewhyc.top.key`, extract and rename:

```powershell
# Extract the zip
Expand-Archive -Path "E:\SSL\25145853_andrewhyc.top_nginx.zip" -DestinationPath "E:\SSL\extracted"

# Create the expected directory structure
New-Item -ItemType Directory -Path "E:\SSL\live\andrewhyc.top" -Force | Out-Null

# Copy and rename: .pem -> fullchain.pem, .key -> privkey.pem
Copy-Item "E:\SSL\extracted\andrewhyc.top.pem" "E:\SSL\live\andrewhyc.top\fullchain.pem"
Copy-Item "E:\SSL\extracted\andrewhyc.top.key" "E:\SSL\live\andrewhyc.top\privkey.pem"

# Cleanup
Remove-Item "E:\SSL\extracted" -Recurse
```

After that the file layout matches what the container expects:

```
E:\SSL\live\andrewhyc.top\fullchain.pem
E:\SSL\live\andrewhyc.top\privkey.pem
```

#### Self-signed certs for testing

```bash
mkdir -p certs/live/andrewhyc.top
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/live/andrewhyc.top/privkey.pem \
  -out certs/live/andrewhyc.top/fullchain.pem \
  -subj "/CN=andrewhyc.top"
SSL_CERT_DIR=$(pwd)/certs docker compose -f infra/docker-compose.prod.yml up -d
```

### 4. Firewall / Ports

Open these ports on your server firewall:

| Port | Purpose              |
|------|----------------------|
| 80   | HTTP (redirect + ACME) |
| 443  | HTTPS (production)     |

```bash
# Linux (ufw)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

```powershell
# Windows (admin PowerShell)
New-NetFirewallRule -DisplayName "Allow HTTP 80" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Allow HTTPS 443" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

Do **not** expose Postgres (5432), Redis (6379), or the API (8000).

### 5. Deploy

```bash
# Validate compose file
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production config

# Build and start all services
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up --build -d

# Run database migrations
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head
```

### 6. Health Check

```bash
# Health endpoint (HTTP → nginx redirects to HTTPS)
curl -k https://localhost/healthz

# Expected: {"status":"ok"}

# SPA loads
curl -k -o /dev/null -w "%{http_code}" https://localhost/
# Expected: 200

# API responds
curl -k https://localhost/openapi.json
# Expected: JSON response with OpenAPI schema (confirms API routing is operational)

# API docs pages
curl -k -o /dev/null -w "%{http_code}" https://localhost/docs
# Expected: 200

curl -k -o /dev/null -w "%{http_code}" https://localhost/redoc
# Expected: 200
```

### 7. Verify the SPA

Access `https://andrewhyc.top/login` in a browser. You should see the AgentNet login page.

## Common Operations

### View Logs

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f nginx
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f api
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f web
```

### Run Migrations

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head
```

### Check Migration Status

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic current
```

### Shell into Services

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api /bin/bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec postgres psql -U agentnet agentnet
```

### Stop

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production down
```

This keeps named volumes. Do not use `--volumes` unless you intend to delete all data.

## Upgrade

```bash
# Pull or copy new code, then:
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production build api web
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up -d
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head

# Verify
curl -k https://localhost/healthz
```

## Rollback

Rollback requires a known-good code version and compatible database state.

```bash
# 1. Stop services
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production down

# 2. Checkout known-good version
git checkout <known-good-tag-or-commit>

# 3. Rebuild and start
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up --build -d

# 4. Verify
curl -k https://localhost/healthz
```

> ⚠️ If the failed release included database migrations, you must first revert them.
> Alembic downgrade: `docker compose exec api alembic downgrade -1`
> See `docs/backup-restore.md` for full database rollback procedure (when available).

## Observability

Prometheus + Grafana are available under the `observability` profile:

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production --profile observability up -d
```

Grafana binds to `127.0.0.1:3000`. Access via SSH tunnel:

```bash
ssh -L 3000:127.0.0.1:3000 user@andrewhyc.top
# Then open http://localhost:3000
```

## Security Notes

- Never commit `infra/.env.production`
- Generate strong random passwords (use `openssl rand -base64 24` or `pwsh -Command "[System.Security.Cryptography.RandomNumberGenerator]::GetHexString(24)"`)
- Keep Postgres, Redis, and API ports internal (not exposed to host)
- Restrict `/metrics` access (already configured in nginx)
- Uncomment the `Strict-Transport-Security` header after confirming TLS works
- Rotate API keys and agent tokens periodically
- Review audit logs regularly

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `connection refused` | Service not started | `docker compose ps` to check |
| `502 bad gateway` | nginx can't reach api/web | Check `docker compose logs nginx` |
| SSL error | Cert path wrong or missing | Verify `SSL_CERT_DIR` and file layout |
| SPA blank page | Wrong API base URL | Check VITE_AGENTNET_API_BASE if set |
| `certificate has expired` | Let's Encrypt renewal | `sudo certbot renew` |
