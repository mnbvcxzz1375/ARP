"""agentnet agent commands."""

from __future__ import annotations

import click
from agentnet import Client, AgentNetError

from ..config import ConfigManager

SENSITIVE_FIELDS = {"agent_token"}


@click.group()
def agent() -> None:
    """Manage agents."""


@agent.command("create")
@click.option("--name", prompt=True, help="Agent name")
@click.option("--runtime", prompt=True, default="python", help="Runtime type")
@click.option("--description", default=None, help="Agent description")
@click.option("--capability", "-c", multiple=True, help="Capabilities (repeatable)")
@click.option("--inbound-policy", default="request_approval",
              type=click.Choice(["private", "contacts_only", "request_approval", "public"]))
@click.option("--discoverable/--no-discoverable", default=False)
def create_agent(
    name: str,
    runtime: str,
    description: str | None,
    capability: tuple[str, ...],
    inbound_policy: str,
    discoverable: bool,
) -> None:
    """Create a new agent."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.create_agent(
                name=name,
                runtime=runtime,
                description=description,
                capabilities=list(capability) if capability else [],
                inbound_policy=inbound_policy,
                discoverable=discoverable,
            )
            click.echo("Agent created:")
            click.echo(f"  Agent ID:     {result['agent_id']}")
            click.echo(f"  Agent Number: {result['agent_number']}")
            if result.get("agent_token"):
                click.secho(f"  Agent Token:  {result['agent_token']}", fg="yellow", err=True)
                click.secho("  >>> Save this token now — it will NOT be shown again! <<<", fg="red", bold=True, err=True)
            click.echo(f"  Name:         {result['name']}")
            click.echo(f"  Status:       {result['status']}")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@agent.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.option("--search", default=None, help="Search by name")
@click.option("--page", default=1, help="Page number")
def list_agents(status: str | None, search: str | None, page: int) -> None:
    """List your agents."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.list_agents(page=page, status=status, search=search)
            click.echo(f"Agents ({result['total']} total):")
            for a in result["agents"]:
                click.echo(f"  [{a['status']:8s}] {a['name']:20s}  {a['agent_number']}  ({a['agent_id']})")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@agent.command("get")
@click.argument("agent_id")
def get_agent(agent_id: str) -> None:
    """Get agent details."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.get_agent(agent_id)
            click.echo("Agent:")
            for key, val in result.items():
                if key in SENSITIVE_FIELDS:
                    val = "***REDACTED***"
                click.echo(f"  {key}: {val}")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@agent.command("rotate-token")
@click.argument("agent_id")
@click.confirmation_option(prompt="This will revoke the old token. Continue?")
def rotate_token(agent_id: str) -> None:
    """Rotate agent token (invalidate old, get new)."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.rotate_token(agent_id)
            click.secho(f"New Token: {result['agent_token']}", fg="yellow", err=True)
            click.secho(">>> Save this token now — old token is revoked! <<<", fg="red", bold=True, err=True)
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)
