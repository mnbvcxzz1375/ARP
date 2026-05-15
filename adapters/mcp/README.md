# AgentNet MCP Adapter

MCP is reserved as an adapter layer for the MVP. The future adapter will wrap an
MCP server as an AgentNet tool agent with an Agent Number, expose tool metadata
as capabilities, translate `task.request` into MCP tool calls, and translate MCP
results back into ARP `task.result` messages.

The core Agent Relay Protocol remains responsible for identity, routing, task
state, connection approval, and authorization.

