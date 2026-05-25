# HTTPS/WSS Verification Report — andrewhyc.top

## Prerequisites

- Python 3.11+ with `httpx` and optionally `websockets` packages
- Internet access to the target domain
- Set `DOMAIN` env var to override target domain (default: `andrewhyc.top`)
- Set `WS_PATH` env var to override WebSocket path (default: `/v1/ws`)

## How to Run

```bash
cd scripts/validation
pip install httpx websockets
python verify_https_wss.py
# or with custom domain:
python verify_https_wss.py --domain yourdomain.example
```

## Expected Results

| Check | Expected Outcome | Notes |
|-------|-----------------|-------|
| HTTPS homepage | PASS — 200/301/302 | nginx serves SPA or redirects |
| TLS certificate | PASS — valid chain, not expired | TLS 1.2/1.3 per nginx config |
| /healthz | PASS or SKIP | If exposed via nginx, returns 200 `{"status":"alive"}`; if restricted to internal networks, returns 404/403 — document as expected |
| WSS /v1/ws | PASS — 401/403 with auth required | WSS upgrade should work; unauthenticated connection should be rejected with proper error, not silently dropped |

## Reverse Proxy Policy for Health Endpoints

Per the nginx config (`infra/nginx/agentnet.conf`), the `/metrics` endpoint is restricted to private networks. Health endpoints (`/healthz`, `/readyz`) are configured as public on the API side (no auth required). If they are not accessible externally, it means the nginx config restricts them — this should be documented as a deliberate policy choice, not treated as a failure.

Production recommendation: Expose `/healthz` (liveness) and `/readyz` (readiness) through nginx for external monitoring tools, but keep `/metrics` restricted.

## Status

**Requires external environment** — this script must be run against a live deployment. The results will vary based on deployment state and network topology. Cannot be verified in CI without a deployed target.