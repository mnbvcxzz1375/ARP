"""agentnet CLI — manage agents, tasks, and approvals on the AgentNet Relay Platform."""

from __future__ import annotations

import click

from .commands.login import login
from .commands.agent_cmd import agent
from .commands.task_cmd import task
from .commands.connect_cmd import connect
from .commands.approve_cmd import approve
from .commands.key_cmd import key


@click.group()
@click.version_option(version="0.1.0", prog_name="agentnet")
def main() -> None:
    """AgentNet CLI — Agent-to-Agent Relay Platform.

    Manage agents, send tasks, handle approvals, and connect agents
    to the relay via WebSocket.

    Quick start:
      agentnet login                Configure credentials
      agentnet agent create         Create a new agent
      agentnet connect              Connect an agent to the relay
      agentnet task send <agent>    Send a task to an agent
      agentnet approve list         View pending approvals
    """


main.add_command(login)
main.add_command(agent)
main.add_command(task)
main.add_command(connect)
main.add_command(approve)
main.add_command(key)


if __name__ == "__main__":
    main()
