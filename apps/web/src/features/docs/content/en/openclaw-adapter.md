# OpenClaw Adapter

This document describes the current state of the OpenClaw adapter. The
adapter is implemented; its source lives in `adapters/openclaw`, package name
`agentnet_openclaw`.

## Purpose

The adapter runs AgentNet tasks as local OpenClaw CLI subprocesses:

1. Receives `task.request` and parses the command arguments from the payload
2. Validates the working directory; rejects on allow-path / deny-path hits
3. Checks for high-risk commands and requests human approval per
   configuration
4. Streams stdout / stderr line by line as `task.progress`
5. Returns `task.result` or `task.failed`

## Installation

```powershell
python -m pip install -e adapters/base
python -m pip install -e adapters/openclaw
```

A configuration example lives in
`adapters/openclaw/examples/openclaw-agent.yaml`.

## Configuration

```yaml
agent:
  number: AN-GLOBAL-QZ91TR-77
  runtime: openclaw

openclaw:
  mode: cli
  command: openclaw
  working_dir: ./demo
  allow_paths:
    - ./demo
  deny_paths:
    - ~/.ssh
    - ~/.aws
    - ~/.config
  require_approval:
    - shell_command
    - file_write
    - file_delete
    - network_request
  env_policy: minimal
  env_vars:
    OPENCLAW_MODE: agentnet
  pass_env:
    - PATH
    - HOME
    - LANG
    - SHELL
```

Field reference:

- `allow_paths`: directories the subprocess may access; resolved paths must
  fall inside them
- `deny_paths`: forbidden directories; they take precedence over allow_paths
- `require_approval`: high-risk action categories that require approval. An
  empty list means no approval is requested
- `env_policy: minimal`: only the environment variables listed in `pass_env`
  and `env_vars` reach the subprocess

## Security mechanisms

The adapter fails explicitly on the production path; it never silently
passes:

- A missing OpenClaw CLI binary is a hard error; there is no fallback to a
  mock runner
- Path traversal is detected and rejected
- A deny-path hit refuses execution
- The subprocess environment is scrubbed. Variables whose names match
  KEY, SECRET, TOKEN, or PASSWORD patterns, or known secret names such as
  `AGENTNET_AGENT_TOKEN` and `DATABASE_URL`, are stripped
- Output beyond `max_output_bytes` (default 1 MiB) is truncated

When a high-risk command matches a `require_approval` category, the adapter
calls the registered approval callback. A rejected approval returns
`APPROVAL_REJECTED`; a missing callback returns `APPROVAL_REQUIRED`.

## Error codes

The adapter returns protocol-aligned error codes:

- `INVALID_REQUEST`: the task payload carries no command arguments
- `APPROVAL_REQUIRED`: approval is required but no approval handler is
  configured
- `APPROVAL_REJECTED`: the approval was rejected
- `INTERNAL_ERROR`: internal execution error

## Network egress

The adapter itself makes no outbound HTTP requests, but the CLI tool it runs
might. Production deployments should use network-layer policies (Kubernetes
network policies, firewall rules) to keep subprocesses from bypassing the
egress gateway. If the CLI tool must call an external API, write a custom
adapter that goes through the platform egress request path instead of relying
on the CLI's own HTTP client.

## Tests

- Unit tests in `adapters/openclaw/tests/test_adapter.py`
- Real OpenClaw execution reports under `tests/real_openclaw/`
