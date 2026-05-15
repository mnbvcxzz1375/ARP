# AgentNet OpenClaw Adapter

Phase 0 provides the package shell and a typed config draft. Phase 9 will turn
remote `task.request` messages into local OpenClaw CLI executions, stream output
as `task.progress`, and require human approval for high-risk actions.

If a real OpenClaw CLI is unavailable, Phase 9 should include a mock runner so
the relay loop can still be tested end to end.

