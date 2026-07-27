"""goga usages command group.

The ``usages`` group is a ``click.Group`` container for usages subcommands
registered on the root ``app`` in ``goga/cli.py``. The ``sync`` subcommand
synchronizes cell-level usages from declared git dependencies.
"""

from __future__ import annotations

import click
import yaml

from ...usages import sync as sync_logic


@click.group()
def usages() -> None:
    """Manage cell-level usages synchronized from git dependencies."""


@usages.command("sync")
@click.option("--force", "-f", is_flag=True, default=False, help="Clean .goga/usages/ then re-sync all deps.")
@click.pass_context
def sync(ctx: click.Context, force: bool) -> None:
    """Synchronize cell-level usages from declared git dependencies.

    Reads the ``usages`` section of ``.goga/config.yml`` and, for each declared
    ``<group>/<dep>`` git dependency, clones the repository and deploys its
    cell-level usages into ``.goga/usages/<group>/<dep>/``.

    Args:
        ctx: Click execution context used to control process exit codes.
        force: When set, clear ``.goga/usages/`` (except ``cooks`` and root
            files) and re-sync every dep; otherwise sync incrementally, skipping
            deps whose target directory already exists.

    Raises:
        click.ClickException: When the configuration file cannot be loaded or
            parsed (FileNotFoundError, KeyError, ValueError, yaml.YAMLError
            propagated from ``sync_logic``).
    """
    try:
        exit_code = sync_logic(force)
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    ctx.exit(exit_code)
