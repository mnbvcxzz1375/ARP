"""agentnet connect command — runs the agent runtime."""

from __future__ import annotations

import asyncio
import click
from agentnet import Agent, AgentNetError, TaskContext

from ..config import ConfigManager


@click.command()
@click.option("--token", default=None, help="Agent token (or use AGENTNET_AGENT_TOKEN env var)")
@click.option("--base-url", default=None, help="Relay base URL")
def connect(token: str | None, base_url: str | None) -> None:
    """Connect as an agent to the relay (WebSocket).

    Uses the built-in echo handler if no task_handler is defined.
    Use the SDK programmatic API for custom handlers.
    """
    cfg = ConfigManager()
    url = base_url or cfg.base_url
    tk = token or cfg.agent_token or ""

    if not tk or not tk.startswith("agt_sk_"):
        click.secho(
            "Error: agent token required. Set AGENTNET_AGENT_TOKEN or use --token.",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    agent = Agent(base_url=url, agent_token=tk)

    @agent.task_handler
    async def echo(ctx: TaskContext):
        await ctx.accept()
        await ctx.progress("Echo agent received task", progress_pct=10)
        await asyncio.sleep(0.5)
        await ctx.result({"echo": ctx.payload, "agent": "cli-connect"})

    click.echo(f"Connecting to {url}...")
    try:
        agent.run()
    except KeyboardInterrupt:
        click.echo()
        click.echo("Disconnected.")
    except AgentNetError as exc:
        click.secho(f"Error: {exc}", fg="red", err=True)
        raise SystemExit(1)
    except (ConnectionError, OSError) as exc:
        click.secho(f"Connection error: {exc}", fg="red", err=True)
        raise SystemExit(1)
