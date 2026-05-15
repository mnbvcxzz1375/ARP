# Architecture

AgentNet is organized as a monorepo with four main areas:

- `apps/api`: FastAPI relay backend.
- `apps/cli`: future local command line tool.
- `packages/python-sdk`: future Python client and agent runtime.
- `adapters`: OpenClaw and MCP adapter packages.

The backend keeps routing, identity, task state, approval, and authorization in
the relay. Adapters translate external agent frameworks into the Agent Relay
Protocol instead of replacing the core protocol.

Phase 0 provides only the engineering skeleton. Phase 1 adds persistent users,
API keys, agents, and agent tokens.

