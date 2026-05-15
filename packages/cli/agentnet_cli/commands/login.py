"""agentnet login command."""

from __future__ import annotations

import click

from ..config import ConfigManager


@click.command()
@click.option("--base-url", default=None, help="Relay API base URL")
@click.option("--api-key", prompt=True, hide_input=True, help="API key (an_key_...)")
def login(base_url: str | None, api_key: str) -> None:
    """Configure credentials for the AgentNet relay."""
    try:
        cfg = ConfigManager()
        url = base_url or click.prompt("Base URL", default=cfg.base_url)
        cfg.set_credentials(url, api_key)
        click.echo(f"[OK] Logged in to {url}")
        click.echo(f"Config saved to: {cfg.path}")
    except OSError as exc:
        click.secho(f"Error writing config: {exc}", fg="red", err=True)
        raise SystemExit(1)
