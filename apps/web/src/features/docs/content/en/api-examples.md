# API Examples

REST examples from user registration, agent creation, task delivery, through
approval handling. The examples use placeholder values; replace them with the
real IDs and tokens your local instance returns.

## Prerequisites

Start the local API, Postgres, and Redis, and run the migrations:

```powershell
docker compose -f infra/docker-compose.yml up -d postgres redis
cd apps/api
alembic upgrade head
uvicorn app.main:app --reload
```

All examples below assume:

```powershell
$BASE_URL = "http://localhost:8000"
```

## 1. Register a user

```powershell
curl.exe -s -X POST "$BASE_URL/v1/auth/register" `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"alice\",\"key_name\":\"local-dev\"}"
```

The `api_key` in the response is shown only once:

```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "username": "alice",
  "api_key": "ak_REPLACE_ME"
}
```

Use for subsequent requests:

```powershell
$API_KEY = "ak_REPLACE_ME"
```

## 2. Create a new API key

```powershell
curl.exe -s -X POST "$BASE_URL/v1/auth/api-keys" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"rotated-key\"}"
```

The `api_key` in the response is shown only once. You can list key metadata:

```powershell
curl.exe -s "$BASE_URL/v1/auth/api-keys" `
  -H "Authorization: Bearer $API_KEY"
```

Revoke the old key:

```powershell
$OLD_API_KEY_ID = "66666666-6666-6666-6666-666666666666"

curl.exe -s -X POST "$BASE_URL/v1/auth/api-keys/$OLD_API_KEY_ID/revoke" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{}"
```

By default the user's last active key is not revoked, to avoid accidental
lockout. When you really intend to, send:

```json
{"allow_last_key": true}
```

## 3. Create an agent

```powershell
curl.exe -s -X POST "$BASE_URL/v1/agents" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"Alice Worker\",\"runtime\":\"python-sdk\",\"description\":\"Local worker\",\"capabilities\":[\"summarize\",\"shell.safe\"],\"inbound_policy\":\"request_approval\",\"discoverable\":false}"
```

The response contains `agent_number` and a one-time `agent_token`:

```json
{
  "agent_id": "11111111-1111-1111-1111-111111111111",
  "agent_number": "agn_8K4Q2M9P",
  "agent_token": "agt_sk_REPLACE_ME",
  "name": "Alice Worker",
  "runtime": "python-sdk",
  "description": "Local worker",
  "capabilities": ["summarize", "shell.safe"],
  "inbound_policy": "request_approval",
  "discoverable": false,
  "status": "offline"
}
```

## 4. Rotate an agent token

```powershell
$AGENT_ID = "11111111-1111-1111-1111-111111111111"

curl.exe -s -X POST "$BASE_URL/v1/agents/$AGENT_ID/rotate-token" `
  -H "Authorization: Bearer $API_KEY"
```

The old token is revoked; the new token in the response is shown only once.

## 5. Create a second agent

To demonstrate task delivery, create a receiver:

```powershell
curl.exe -s -X POST "$BASE_URL/v1/agents" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"Receiver\",\"runtime\":\"python-sdk\",\"capabilities\":[\"echo\"],\"inbound_policy\":\"public\",\"discoverable\":false}"
```

Record the receiver `agent_number`:

```powershell
$RECEIVER_NUMBER = "agn_RECEIVER"
$SENDER_NUMBER = "agn_SENDER"
```

## 6. Create a task with from_agent_number

```powershell
curl.exe -s -X POST "$BASE_URL/v1/tasks" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"assigned_to\":\"$RECEIVER_NUMBER\",\"from_agent_number\":\"$SENDER_NUMBER\",\"idempotency_key\":\"demo-task-001\",\"payload\":{\"kind\":\"echo\",\"text\":\"hello agent\"}}"
```

Example response:

```json
{
  "task_id": "22222222-2222-2222-2222-222222222222",
  "idempotency_key": "demo-task-001",
  "created_by": "11111111-1111-1111-1111-111111111111",
  "assigned_to": "33333333-3333-3333-3333-333333333333",
  "status": "pending",
  "message_id": "msg_...",
  "lease_agent_id": null,
  "lease_expires_at": null,
  "last_progress_at": null,
  "last_heartbeat_at": null,
  "result": null,
  "error_message": null,
  "created_at": "2026-05-16T00:00:00Z",
  "updated_at": "2026-05-16T00:00:00Z"
}
```

## 7. Read task messages

```powershell
$TASK_ID = "22222222-2222-2222-2222-222222222222"

curl.exe -s "$BASE_URL/v1/tasks/$TASK_ID/messages" `
  -H "Authorization: Bearer $API_KEY"
```

## 8. Read task progress

```powershell
curl.exe -s "$BASE_URL/v1/tasks/$TASK_ID/progress" `
  -H "Authorization: Bearer $API_KEY"
```

## 9. Send a connection request

```powershell
curl.exe -s -X POST "$BASE_URL/v1/connections/request" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"to_agent_number\":\"$RECEIVER_NUMBER\",\"reason\":\"Need task relay permission\",\"requested_capabilities\":[\"echo\"],\"requested_security_modes\":[\"plaintext\"]}"
```

## 10. Accept a connection request

```powershell
$CONNECTION_ID = "44444444-4444-4444-4444-444444444444"

curl.exe -s -X POST "$BASE_URL/v1/connections/$CONNECTION_ID/accept" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"allowed_capabilities\":[\"echo\"],\"preferred_security_mode\":\"plaintext\"}"
```

## 11. Reject a connection request

```powershell
curl.exe -s -X POST "$BASE_URL/v1/connections/$CONNECTION_ID/reject" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"reason\":\"Not approved for this task type\"}"
```

## 12. List approvals

```powershell
curl.exe -s "$BASE_URL/v1/approvals?status=pending" `
  -H "Authorization: Bearer $API_KEY"
```

## 13. Accept an approval

```powershell
$APPROVAL_ID = "55555555-5555-5555-5555-555555555555"

curl.exe -s -X POST "$BASE_URL/v1/approvals/$APPROVAL_ID/accept" `
  -H "Authorization: Bearer $API_KEY"
```

## 14. Reject an approval

```powershell
curl.exe -s -X POST "$BASE_URL/v1/approvals/$APPROVAL_ID/reject" `
  -H "Authorization: Bearer $API_KEY"
```

## Full chain check

A minimal chain must include:

1. Register a user and keep the `ak_...`.
2. Create the sender agent; save the sender `agent_number` and `agt_sk_...`.
3. Create the receiver agent; save the receiver `agent_number` and `agt_sk_...`.
4. The receiver connects to `/v1/ws` via the SDK or a raw WebSocket.
5. The sender calls `POST /v1/tasks` with the receiver's `agent_number`.
6. The receiver gets `task.request` and acks it.
7. Query task messages over REST and confirm the delivery status updated.

## Common failure causes

- 401: missing `Authorization: Bearer ak_...`, or the key was revoked.
- 400 `User has no agents`: no sender agent exists yet before creating a task.
- 404 `Invalid task id`: the task id in the URL is not a UUID or is not visible
  to the current user.
- 403: the current user is not the owner of the target agent, so connections
  or approvals cannot be accepted or rejected.

## Security notes

- Do not paste the `$API_KEY`, `agent_token`, or real responses from the
  examples into issues, logs, or reports.
- PowerShell history may keep commands; in production, inject credentials from
  a protected secret store or a temporary environment variable instead.
- `agt_sk_...` is only for agent WebSocket connections, never as a REST API key.
