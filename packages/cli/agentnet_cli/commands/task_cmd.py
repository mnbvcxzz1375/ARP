"""agentnet task commands."""

from __future__ import annotations

import json as _json
import time as _time

import click
from agentnet import Client, AgentNetError

from ..config import ConfigManager


@click.group()
def task() -> None:
    """Manage tasks."""


@task.command("send")
@click.argument("agent_number")
@click.option("--message", "-m", default=None, help="Simple text message")
@click.option("--payload", "-p", default=None, help="JSON payload")
@click.option("--wait/--no-wait", default=True, help="Wait for result")
@click.option("--timeout", default=60, help="Max seconds to wait")
@click.option("--idempotency-key", default=None, help="Idempotency key")
@click.option("--from-agent-number", default=None, help="Sender agent number")
def send_task(
    agent_number: str,
    message: str | None,
    payload: str | None,
    wait: bool,
    timeout: int,
    idempotency_key: str | None,
    from_agent_number: str | None,
) -> None:
    """Send a task to an agent."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        payload_dict = {}
        if message:
            payload_dict["message"] = message
        if payload:
            try:
                payload_dict.update(_json.loads(payload))
            except _json.JSONDecodeError:
                click.secho("Error: Invalid JSON payload", fg="red", err=True)
                raise SystemExit(1)

        try:
            task_result = client.create_task(
                assigned_to=agent_number,
                from_agent_number=from_agent_number,
                payload=payload_dict,
                idempotency_key=idempotency_key,
            )
            task_id = task_result["task_id"]
            click.echo(f"Task created: {task_id} (status={task_result['status']})")

            if not wait:
                return

            click.echo("Waiting for result...", nl=False)
            for _ in range(timeout):
                _time.sleep(1)
                click.echo(".", nl=False)
                updated = client.get_task(task_id)
                status = updated["status"]
                if status == "completed":
                    click.echo()
                    click.secho(f"[OK] Task completed", fg="green")
                    click.echo(f"Result: {updated.get('result')}")
                    return
                if status in ("failed", "cancelled", "rejected", "expired"):
                    click.echo()
                    click.secho(
                        f"[FAIL] Task {status}: {updated.get('error_message', 'no message')}",
                        fg="red", err=True,
                    )
                    return

            click.echo()
            click.secho(f"Timed out after {timeout}s", fg="yellow", err=True)
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@task.command("get")
@click.argument("task_id")
def get_task(task_id: str) -> None:
    """Get task details."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            t = client.get_task(task_id)
            click.echo(f"Task {task_id}:")
            for key in ("status", "created_by", "assigned_to", "result", "error_message",
                         "created_at", "updated_at"):
                val = t.get(key)
                if val is not None:
                    click.echo(f"  {key}: {val}")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@task.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--limit", default=20, help="Page size")
def list_tasks(status: str | None, offset: int, limit: int) -> None:
    """List your tasks."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            result = client.list_tasks(status=status, offset=offset, limit=limit)
            click.echo(f"Tasks ({result['total']} total):")
            for t in result["tasks"]:
                click.echo(f"  [{t['status']:12s}] {t['task_id']}  -> {t.get('assigned_to', '?')}")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)


@task.command("logs")
@click.argument("task_id")
@click.option("--limit", default=50, help="Max entries")
def task_logs(task_id: str, limit: int) -> None:
    """View task progress logs."""
    cfg = ConfigManager()
    with Client(cfg.base_url, cfg.api_key) as client:
        try:
            progs = client.get_task_progress(task_id, limit=limit)
            click.echo(f"Progress entries ({progs['total']}):")
            for p in progs.get("entries", []):
                click.echo(f"  seq={p['seq']:3d}  [{p.get('progress_pct', '?')}%]  {p.get('message', '')}")
        except AgentNetError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            raise SystemExit(1)
