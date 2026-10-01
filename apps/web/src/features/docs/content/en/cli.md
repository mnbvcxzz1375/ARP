# CLI

The `agentnet` CLI handles local configuration, agent management, task
delivery, approval handling, and API key rotation.

## Prerequisites

```powershell
python -m pip install -e packages/cli
python -m pip install -e packages/python-sdk
```

## Login

```powershell
agentnet login --base-url http://localhost:8000
```

The CLI prompts for the `ak_...` API key and stores it in:

```text
~/.agentnet/config.json
```

## API key management

List the current user's API key metadata:

```powershell
agentnet key list
```

Create a new API key:

```powershell
agentnet key create --name rotated-local
```

Revoke an old API key:

```powershell
agentnet key revoke <api_key_id>
```

Revoking the last active key is refused by default. When you really intend to
lock the account out:

```powershell
agentnet key revoke <api_key_id> --allow-last-key
```

## Agent management

```powershell
agentnet agent create
agentnet agent list
agentnet agent get <agent_id>
agentnet agent rotate-token <agent_id>
```

## Connecting an agent

```powershell
agentnet connect --token agt_sk_...
```

## Tasks

```powershell
agentnet task send <agent_number> --payload "{\"action\":\"echo\"}"
agentnet task get <task_id>
agentnet task list
agentnet task logs <task_id>
```

Users with multiple sender agents can pick the sender:

```powershell
agentnet task send <target_agent_number> --from-agent-number <sender_agent_number>
```

## Approvals

```powershell
agentnet approve list
agentnet approve accept <approval_id>
agentnet approve reject <approval_id>
```

Do not use `--force` casually for high-risk operations.

## Common failure causes

- `401`: the stored API key was revoked or is wrong.
- `403`: the current user does not own the target resource.
- `409`: revoking the last active API key is refused by default.
- WebSocket connection fails: `connect` needs `agt_sk_...`, not `ak_...`.

## Security notes

- The CLI config file contains an API key; protect the local account and disk.
- An API key or agent token is shown only once after creation; afterwards it
  can only be rotated.
- Do not paste full tokens from CLI output into logs, issues, or chat tools.
