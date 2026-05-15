"""agentnet approve command — human-in-the-loop approvals."""

from __future__ import annotations

import click
from agentnet import Client, AgentNetError

from ..config import ConfigManager


@click.group()
def approve() -> None:
    """Manage human-in-the-loop approvals."""


@approve.command("list")
@click.option("--status", default=None, help="Filter (pending/accepted/rejected/expired)")
def list_approvals(status: str | None) -> None:
    """List pending approvals."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.list_approvals(status=status)
            click.echo(f"Approvals ({result.get('total', 0)} total):")
            for a in result.get("approvals", []):
                risk_color = "red" if a.get("risk_level") == "high" else "yellow"
                click.echo(
                    f"  [{a['id']}] "
                    f"task={a.get('task_id', '?')} "
                    f"risk={click.style(a.get('risk_level', '?'), fg=risk_color)} "
                    f"action={a.get('action_kind', '?')} "
                    f"status={a.get('status', '?')}"
                )
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


def _show_approval_context(client: Client, approval_id: str) -> None:
    """Fetch and display approval details for user confirmation."""
    approvals = client.list_approvals()
    for a in approvals.get("approvals", []):
        if a.get("id") == approval_id:
            risk = a.get("risk_level", "?")
            risk_color = "red" if risk == "high" else "yellow"
            click.echo()
            click.echo(f"  Approval ID:  {a['id']}")
            click.echo(f"  Task ID:      {a.get('task_id', '?')}")
            click.echo(f"  Risk Level:   {click.style(risk.upper(), fg=risk_color, bold=True)}")
            click.echo(f"  Action:       {a.get('action_kind', '?')}")
            click.echo(f"  Status:       {a.get('status', '?')}")
            if a.get("reason"):
                click.echo(f"  Reason:       {a['reason']}")
            click.echo()
            if risk == "high":
                click.secho(
                    "  !! HIGH RISK — this action could be dangerous. Review carefully before accepting.",
                    fg="red", bold=True,
                )
                click.echo()
            return
    click.secho(f"Warning: Could not load details for approval {approval_id}", fg="yellow", err=True)


@approve.command("accept")
@click.argument("approval_id")
@click.option("--force/--no-force", default=False, help="Skip confirmation")
def accept_approval_cmd(approval_id: str, force: bool) -> None:
    """Accept a pending approval."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        if not force:
            _show_approval_context(client, approval_id)
            if not click.confirm("Are you sure you want to ACCEPT this approval?"):
                click.echo("Aborted.")
                return

        try:
            client.accept_approval(approval_id)
            click.secho(f"[OK] Approval {approval_id} accepted", fg="green")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@approve.command("reject")
@click.argument("approval_id")
@click.option("--force/--no-force", default=False, help="Skip confirmation")
def reject_approval_cmd(approval_id: str, force: bool) -> None:
    """Reject a pending approval."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        if not force:
            _show_approval_context(client, approval_id)
            if not click.confirm("Are you sure you want to REJECT this approval?"):
                click.echo("Aborted.")
                return

        try:
            client.reject_approval(approval_id)
            click.secho(f"[OK] Approval {approval_id} rejected", fg="yellow")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)
