"""goga usages command group.

The ``usages`` group is a ``click.Group`` container for usages subcommands
registered on the root ``app`` in ``goga/cli.py``. The ``sync`` subcommand
(config-driven synchronization of cell-level usages) is added in Task 11.
"""

import click


@click.group()
def usages() -> None:
    """Manage cell-level usages synchronized from git dependencies."""
