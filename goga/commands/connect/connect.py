from __future__ import annotations

import click

from ...connect import connect as connect_logic


@click.command()
@click.argument("agents", nargs=-1, required=True)
@click.option("--force-overwrite", is_flag=True, default=False, help="Overwrite existing tool skills")
@click.pass_context
def connect(ctx: click.Context, agents: tuple[str, ...], force_overwrite: bool) -> None:
    """Connect goga skills and commands to one or more AI agent configurations.

    \b
    Usage:
      goga connect claude
      goga connect codex
      goga connect claude codex cursor

    \b
    Arguments:
      agents          - one or more target AI agent names (required)

    \b
    Options:
      --force-overwrite - overwrite existing tool skills without prompting

    Exit codes: 0 on success, 1 on error (unsupported agent, resources not found, download failure).
    """
    exit_code = connect_logic(list(agents), force_overwrite=force_overwrite)
    ctx.exit(exit_code)
