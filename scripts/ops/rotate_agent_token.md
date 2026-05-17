# Rotate Agent Token Runbook

## Purpose

Rotate one Agent token using the real API and verify that the old token no longer works.

## Inputs

```powershell
$env:PUBLIC_BASE_URL = "https://example.com"
$env:API_KEY = "ak_REPLACE_ME"
$env:AGENT_ID = "agent-uuid"
```

## Steps

```powershell
curl.exe -s -X POST "$env:PUBLIC_BASE_URL/v1/agents/$env:AGENT_ID/rotate-token" `
  -H "Authorization: Bearer $env:API_KEY"
```

Update the Agent runtime with the returned `agent_token`, restart the Agent, and verify WebSocket connection.

## Audit

Record Agent ID, Agent Number, token prefix only, operator, time, and validation result.
