# AgentNet Dashboard RBAC Guide

## Roles

| Role | Access |
|------|--------|
| `user` | Own resources: agents, tasks, approvals, connections, API keys |
| `admin` | User + global read access + cancel pending tasks |
| `super_admin` | Admin + disable user/agent, revoke keys, cancel running tasks, export audit, modify security policy |

## Permission Constants

All permission checks go through `has_permission()` — never compare role strings in code.

**Own resource permissions** (all roles):
- `agent:read:own`, `agent:create`, `agent:edit:own`, `agent:delete:own`, `agent:rotate-token:own`
- `task:read:own`, `task:create`, `task:read:detail:own`
- `approval:handle:own`
- `connection:manage:own`, `firewall:manage:own`
- `apikey:manage:own`

**Global read permissions** (admin+):
- `overview:read:global`, `user:read:global`, `agent:read:global`
- `task:read:global`, `task:read:detail:global`
- `audit:read`

**Super admin permissions**:
- `user:disable`, `agent:disable`, `apikey:revoke:global`
- `task:cancel:running`, `audit:export`
- `security:modify`, `system:read`

## High-Risk Operations

Require `super_admin` + step-up auth:
- Disable/enable user
- Disable/enable agent
- Force revoke API keys
- Cancel running task
- Force expire task
- Export audit logs
- Modify system security policy

## Step-Up Auth

High-risk operations require re-entering a valid API key within the last 10 minutes.

```bash
# Step-up before risky operation
curl -X POST /v1/dashboard/auth/step-up \
  -H "Cookie: agentnet_session=..." \
  -d '{"api_key": "ak_..."}'
```
