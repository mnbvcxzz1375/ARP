# Quickstart

Phase 0 quickstart:

```bash
docker compose -f infra/docker-compose.yml up --build
curl http://localhost:8000/healthz
```

Expected response:

```json
{"status":"ok"}
```

Run tests:

```bash
cd apps/api
python -m pip install -e ".[test]"
pytest
```

Agent creation, WebSocket relay, SDK examples, CLI commands, and OpenClaw
execution are implemented in later phases.

