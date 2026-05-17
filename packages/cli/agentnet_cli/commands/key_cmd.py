"""agentnet key commands."""

from __future__ import annotations

import click
from agentnet import AgentNetError, Client

from ..config import ConfigManager


@click.group(name="key")
def key() -> None:
    """Manage user API keys."""


@key.command("list")
def list_keys() -> None:
    """List API keys for the logged-in user."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.list_api_keys()
            click.echo(f"API keys ({result['total']} total):")
            for item in result["api_keys"]:
                status = "revoked" if item["is_revoked"] else "active"
                expires_at = item["expires_at"] or "never"
                click.echo(
                    f"  [{status:7s}] {item['name']:24s} "
                    f"{item['key_prefix']:16s} {item['api_key_id']} expires={expires_at}"
                )
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@key.command("create")
@click.option("--name", prompt=True, help="API key name")
@click.option("--expires-at", default=None, help="Optional ISO-8601 expiry time")
def create_key(name: str, expires_at: str | None) -> None:
    """Create a new API key."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.create_api_key(name, expires_at=expires_at)
            click.echo("API key created:")
            click.echo(f"  API Key ID: {result['api_key_id']}")
            click.echo(f"  Prefix:     {result['key_prefix']}")
            click.secho(f"  API Key:    {result['api_key']}", fg="yellow", err=True)
            click.secho("  >>> Save this key now — it will NOT be shown again! <<<", fg="red", bold=True, err=True)
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@key.command("revoke")
@click.argument("api_key_id")
@click.option(
    "--allow-last-key",
    is_flag=True,
    help="Allow revoking the final active API key for this user.",
)
@click.confirmation_option(prompt="This will revoke the API key. Continue?")
def revoke_key(api_key_id: str, allow_last_key: bool) -> None:
    """Revoke an API key."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.revoke_api_key(api_key_id, allow_last_key=allow_last_key)
            click.echo("API key revoked:")
            click.echo(f"  API Key ID: {result['api_key_id']}")
            click.echo(f"  Prefix:     {result['key_prefix']}")
            click.echo(f"  Name:       {result['name']}")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)
