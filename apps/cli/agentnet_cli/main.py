import typer

app = typer.Typer(help="AgentNet CLI placeholder for Phase 8.")


@app.callback()
def main() -> None:
    """AgentNet command line interface."""


@app.command()
def version() -> None:
    typer.echo("agentnet-cli 0.1.0")

