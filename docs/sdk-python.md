# Python SDK

The Python SDK is planned for Phase 7. It will provide:

- `Client`
- `Agent`
- `TaskContext`
- `AgentWebSocket`
- `SessionStore`
- `IdempotencyCache`

The target developer experience is:

```python
from agentnet import Agent

agent = Agent.from_env()

@agent.task_handler
async def handle(task):
    await task.accept()
    await task.progress("Started")
    await task.result("Done")

agent.run()
```

