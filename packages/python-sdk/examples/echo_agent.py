"""Example: Echo agent that responds to tasks by echoing the payload.

Usage:
  set AGENTNET_AGENT_TOKEN=agt_sk_...
  set AGENTNET_BASE_URL=http://localhost:8000
  python examples/echo_agent.py
"""

import asyncio
import logging
import os
import sys

# Allow running from repo root without installing the package first
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentnet import Agent, TaskContext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


async def main():
    agent = Agent.from_env()

    @agent.task_handler
    async def echo(ctx: TaskContext):
        """Accept the task, report progress, then echo back the payload."""
        await ctx.accept()
        await ctx.progress("Echo agent received task", progress_pct=10)
        # Simulate work
        await asyncio.sleep(0.5)
        await ctx.progress("Processing...", progress_pct=50)
        await asyncio.sleep(0.5)
        await ctx.progress("Almost done", progress_pct=90)
        await ctx.result({"echo": ctx.payload})

    await agent.start()


if __name__ == "__main__":
    print("Echo agent starting...")
    asyncio.run(main())
