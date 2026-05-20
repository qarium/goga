from __future__ import annotations

import click

from goga.sync import sync as sync_logic


@click.command()
@click.argument("source")
@click.option("--token", default=None, help="Token for private repository authentication")
@click.option("--branch", default=None, help="Branch to clone")
@click.pass_context
def sync(ctx: click.Context, source: str, token: str | None, branch: str | None) -> None:
    """Synchronize .usages/ from a local path or git repository into .goga/usages/deps/<dep_name>/."""
    exit_code = sync_logic(source, token, branch)
    ctx.exit(exit_code)
