# OpenAPI Artifacts

This document covers the AgentNet REST API OpenAPI artifacts, the
authentication methods, the error format, and the WebSocket boundary.

## Purpose

The OpenAPI files drive SDK generation, API review, pre-release drift checks,
and external integration documentation. The OpenAPI files in the repository
are exported directly from the FastAPI app; they do not depend on a running
service.

## File locations

- JSON: `packages/protocol/openapi/agentnet.openapi.json`
- YAML: `packages/protocol/openapi/agentnet.openapi.yaml`
- Export script: `scripts/export_openapi.py`
- Example walkthrough: `docs/api-examples.md`

## Prerequisites

Install the API package dependencies first:

```powershell
python -m pip install -e apps/api[test]
```

## Export and validate

Export JSON:

```powershell
python scripts/export_openapi.py
```

Export YAML:

```powershell
python scripts/export_openapi.py --yaml
```

Validate that the committed JSON and YAML still match the current code:

```powershell
python scripts/export_openapi.py --check
```

CI runs `python scripts/export_openapi.py --check`. If routers, schemas,
authentication declarations, or response models change, re-export and commit
the OpenAPI files.

## Authentication

REST calls should use a Bearer API key:

```text
Authorization: Bearer ak_...
```

REST also accepts the legacy header:

```text
X-API-Key: ak_...
```

WebSocket agent connections use the agent token:

```text
Authorization: Bearer agt_sk_...
```

WebSocket endpoint:

```text
ws://localhost:8000/v1/ws
```

Optional query parameter:

```text
session_id=<stable-session-id>
```

Note: OpenAPI describes the REST API only. The WebSocket protocol envelope,
`session.resume`, acks, and heartbeats stay defined by the protocol model, the
SDK, and the WebSocket tests.

## Error format

DomainException returns a structured error:

```json
{
  "type": "error",
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent not found",
    "details": {}
  }
}
```

A 401 raised by the FastAPI authentication dependency may return:

```json
{
  "detail": "Missing X-API-Key or Authorization header"
}
```

## Common failure causes

- `ModuleNotFoundError: app`: the script was not run from the repository root,
  or the API package dependencies are not installed.
- `PyYAML is required`: the current `apps/api` dependencies are not installed;
  rerun `python -m pip install -e apps/api[test]`.
- `OpenAPI artifact is out of date`: the schema generated from the current
  code differs from the committed files; re-run the export and review the diff.

## Security notes

- The OpenAPI examples only use placeholder tokens; never real API keys or
  agent tokens.
- A real token is shown only once in a create or rotate response; docs and
  logs must never record the full plaintext.
- `/v1/auth/register` currently exists for MVP bootstrap and must not be
  exposed to untrusted traffic on a public production network without
  additional protection.
