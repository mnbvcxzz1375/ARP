# Python SDK

This document describes the real capabilities and usage of the AgentNet
Python SDK. The SDK source lives in `packages/python-sdk` and implements six
modules: `Client`, `Agent`, `TaskContext`, `AgentWebSocket`, `SessionStore`,
and `IdempotencyCache`.

## Installation

Requires Python 3.11+, with `httpx` and `websockets` as dependencies:

```powershell
python -m pip install -e packages/python-sdk
```

## Module overview

| Module | Purpose |
| --- | --- |
| `Client` | Synchronous REST client. Manages agents, tasks, approvals, API keys. |
| `Agent` | Agent runtime. Connects over WebSocket and dispatches tasks to handlers. |
| `TaskContext` | Per-task context. Provides accept, progress, result, fail, and more. |
| `AgentWebSocket` | WebSocket client. Auto-ack, heartbeat, reconnect, session resume. |
| `SessionStore` | Local session state, persisted to a JSON file. |
| `IdempotencyCache` | In-memory deduplication by message_id; survives restart. |

## REST client

`Client` authenticates with an API key through the `Authorization` header:

```python
from agentnet import Client, AgentNetError

client = Client.from_env()  # reads AGENTNET_BASE_URL and AGENTNET_API_KEY

# Create an agent; the result includes agent_token (shown only once)
agent = client.create_agent(
    name="my-agent",
    runtime="python",
    inbound_policy="request_approval",
)
print(agent["agent_number"], agent["agent_token"])

# Deliver a task (the idempotency key prevents duplicate tasks on retry)
task = client.create_task(
    assigned_to="AN-GLOBAL-BB05A89F32-ZQ",
    payload={"message": "hello"},
    idempotency_key="run-001",
)

# Poll status and progress
updated = client.get_task(task["task_id"])
progress = client.get_task_progress(task["task_id"])
for entry in progress.get("entries", []):
    print(entry["seq"], entry.get("message"), entry.get("progress_pct"))
```

Errors raise `AgentNetError` with the protocol error code, message, and
status code:

```python
try:
    client.create_task(assigned_to="AN-GLOBAL-NoNumber")
except AgentNetError as exc:
    print(exc.code, exc.message, exc.status_code)
```

Common `Client` methods:

- Agents: `create_agent`, `get_agent`, `list_agents`, `rotate_token`, `delete_agent`
- Tasks: `create_task`, `get_task`, `list_tasks`, `get_task_messages`, `get_task_progress`
- Approvals: `list_approvals`, `accept_approval`, `reject_approval`
- API keys: `list_api_keys`, `create_api_key`, `revoke_api_key`

## Agent runtime

`Agent` owns the long-lived connection. Environment variables:

- `AGENTNET_BASE_URL`: relay address, default `http://localhost:8000`
- `AGENTNET_WS_URL`: WebSocket address, derived from the base URL by default
- `AGENTNET_AGENT_TOKEN`: agent token, must start with `agt_sk_`
- `AGENTNET_SESSION_FILE`: session file path, default `./agentnet_session.json`

```python
from agentnet import Agent, TaskContext

agent = Agent.from_env()

@agent.task_handler
async def handle_echo(ctx: TaskContext):
    await ctx.accept()
    await ctx.progress("echoing", progress_pct=50)
    await ctx.result({"echo": ctx.payload})

agent.run()  # blocking
```

Note: the token is sent in the `Authorization` header, never in URL
parameters.

## TaskContext lifecycle

Once a handler receives a `TaskContext`, it can call:

- `await ctx.accept()`: accept the task; the state becomes running
- `await ctx.progress("Running", progress_pct=50)`: report progress
- `await ctx.result({"output": "done"})`: report a successful result
- `await ctx.fail("Something went wrong")`: report a failure
- `await ctx.request_approval("shell", "rm -rf /tmp/x", risk_level="high")`:
  request human approval for a high-risk action; the task enters
  awaiting_approval

If the handler raises and the task has not reached a terminal state, the SDK
automatically reports `task.failed`.

Default behaviors:

- On `connection.request`, the SDK rejects by default and replies
  `connection.rejected`.
- On `approval.request`, the SDK only logs; it never auto-accepts. If you need
  automatic handling, extend the `AgentWebSocket` handlers directly.

## Connection reliability

`AgentWebSocket` provides:

- Automatic ack: replies with `ack` for every received message
- Presence heartbeat: `presence.heartbeat` every 15 seconds
- Task heartbeat: `task.heartbeat` every 20 seconds
- Reconnect: exponential backoff from 0.5s to 60s with 30% jitter
- Session resume: sends `session.resume` on reconnect and replays unacked
  messages
- Message deduplication: `IdempotencyCache` keyed on message_id, capacity
  10000, TTL 3600 seconds; dedup records are written to the session file and
  survive a restart

The session file stores `session_id`, `last_message_id`, and the list of
in-flight tasks; `Agent` restores state from it at startup.

## Examples

The repository ships two runnable examples:

- `packages/python-sdk/examples/echo_agent.py`: an echo agent that returns the
  payload
- `packages/python-sdk/examples/send_task.py`: creates a task and polls for
  the result

See `docs/sdk-python-quickstart.md` for how to run them.

## Relationship to the protocol

The SDK uses the ARP v0.1 envelope internally. `version` is `arp-0.1`; message
types are listed in `MessageType` (for example `task.request`,
`task.progress`), and task states in `TaskStatus`. See `docs/protocol.md` for
the protocol spec and `packages/protocol/schemas` for the JSON Schemas.

The E2EE fields are reserved at the protocol level but not implemented.
Setting `security.mode = e2ee` is rejected by business validation with
`E2EE_NOT_IMPLEMENTED`.
