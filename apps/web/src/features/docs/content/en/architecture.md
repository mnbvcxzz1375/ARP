# Architecture

This document describes the real, current structure of AgentNet, mapped
one-to-one to the repository code.

## Positioning

AgentNet is a message relay layer, policy gateway, and audit hub between
agents. The core capabilities live on the relay side: identity, addressing,
task delivery, offline recovery, approvals, and audit. Adapters translate
external agent frameworks into the Agent Relay Protocol; they never replace
the core protocol.

```text
user / operator
    |
    | browser console / CLI / SDK / REST
    v
FastAPI relay API
    |
    |-- auth, API keys, sessions, CSRF, RBAC
    |-- agent registry
    |-- task and message storage
    |-- connection policy
    |-- approvals
    |-- audit logs
    |-- console aggregate APIs
    |
    |------- PostgreSQL
    |------- Redis
    |
    v
WebSocket agent runtime
    |
    v
Python SDK / OpenClaw adapter / future adapters
```

## Repository layout

Current implementation status:

| Path | Description | Status |
| --- | --- | --- |
| `apps/api` | FastAPI relay backend | implemented |
| `apps/web` | React/Vite console | implemented |
| `packages/python-sdk` | Python SDK and agent runtime | implemented |
| `packages/cli` | `agentnet` CLI | implemented |
| `packages/protocol` | JSON Schema and OpenAPI artifacts | implemented |
| `adapters/base` | adapter interface `agentnet_adapter` | implemented |
| `adapters/openclaw` | OpenClaw adapter | implemented |
| `adapters/mcp` | MCP adapter | placeholder, not implemented |
| `infra` | Docker Compose and nginx templates | implemented |

Backend internals:

```text
apps/api/app/
├── routers/        REST, WebSocket, console routers
├── services/       business logic
├── models/         SQLAlchemy models
├── schemas/        Pydantic validation models
├── websocket/      WebSocket manager and runtime helpers
├── workers/        retry and timeout workers
└── protocol/       protocol constants and validators
```

## Backend

The FastAPI relay backend implements:

- PostgreSQL persistence with Alembic-managed migrations
- Redis for caching and queues
- rate limiting, WebSocket runtime, task routing, approvals, audit
- console APIs (personal console and enterprise console)

## Frontend console

The React/Vite console includes:

- Session handling: HttpOnly session cookie, CSRF, session lifecycle,
  step-up verification
- RBAC: `user`, `admin`, `super_admin`
- Personal console: overview, agents, tasks, approvals, connections, API keys,
  local routing
- Enterprise console: relay nodes, route policies, route decisions, egress
  gateways, dedicated channels, network scopes, network zones, SLA and
  continuity, audit, system health

## SDK and CLI

The Python SDK provides `Client` (synchronous REST) and `Agent` (WebSocket
runtime); see `docs/sdk-python.md`. The CLI offers six command groups: login,
agent, task, connect, approve, and key; see `docs/cli.md`.

## Adapters

Adapters connect external frameworks to the relay:

- `adapters/base` defines the `AdapterInterface` contract
- `adapters/openclaw` is implemented and runs tasks as local OpenClaw CLI
  subprocesses
- `adapters/mcp` currently holds only a README and TODOs; not implemented

See `docs/openclaw-adapter.md`.

## Protocol and contracts

- The ARP v0.1 envelope is described in `docs/protocol.md`
- JSON Schemas live in `packages/protocol/schemas`
- The OpenAPI contract lives in `packages/protocol/openapi`; it is exported
  directly from the FastAPI app by `scripts/export_openapi.py`, and CI
  validates that the committed artifacts match the code

## Deployment and operations

- Development and production Docker Compose templates are in `infra/`
- Deployment, checklists, backup and restore, secret rotation, and
  observability each have a dedicated document under `docs/`
