from __future__ import annotations

import click


@click.command()
@click.option("--agent", default="claude", help="Target AI agent")
@click.pass_context
def init(ctx: click.Context, agent: str) -> None:  # noqa: ARG001
    """Install goga skills and commands into the target AI agent configuration."""
    click.echo("init placeholder")
    ctx.exit(0)
