from __future__ import annotations

import click
import yaml

from ...config import load_config
from ...connect import connect as connect_logic


@click.command()
@click.option("--agent", default=None, help="Target AI agent")
@click.option("--force-overwrite", is_flag=True, default=False, help="Overwrite existing tool skills")
@click.pass_context
def connect(ctx: click.Context, agent: str | None, force_overwrite: bool) -> None:
    """Connect goga skills and commands to the target AI agent configuration."""
    try:
        config = load_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    exit_code = connect_logic(agent, config, force_overwrite=force_overwrite)
    ctx.exit(exit_code)
