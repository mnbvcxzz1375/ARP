# OpenClaw Adapter

The OpenClaw adapter is planned for Phase 9. It will receive AgentNet
`task.request` messages, execute OpenClaw locally through a CLI or mock runner,
stream output as `task.progress`, and publish final `task.result` or
`task.failed` messages.

High-risk local actions such as shell commands, file writes, file deletes,
network requests, sensitive path access, long-running tasks, and large output
must trigger human approval.

