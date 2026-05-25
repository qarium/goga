from __future__ import annotations

import click
import yaml

from goga.config import load_config
from goga.install import install as install_logic


@click.command()
@click.option("--agent", default=None, help="Target AI agent")
@click.option("--force-overwrite", is_flag=True, default=False, help="Overwrite existing tool skills")
@click.pass_context
def install(ctx: click.Context, agent: str | None, force_overwrite: bool) -> None:
    """Install goga skills and commands into the target AI agent configuration."""
    try:
        config = load_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    exit_code = install_logic(agent, config, force_overwrite=force_overwrite)
    ctx.exit(exit_code)
