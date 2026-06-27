from __future__ import annotations

import click

from ...sync import sync as sync_logic


@click.command()
@click.argument("source")
@click.option("--token", default=None, help="Token for private repository authentication")
@click.option("--branch", default=None, help="Branch to clone")
@click.pass_context
def sync(ctx: click.Context, source: str, token: str | None, branch: str | None) -> None:
    """Synchronize .usages/ from a local path or git repository into the project deps directory.

    The remote or local `.usages/` tree is mirrored into
    `.goga/usages/deps/<dep_name>/`.

    Args:
        ctx: Click execution context used to control process exit codes.
        source: Local path or git URL of the dependency to synchronize.
        token: Optional authentication token for private repositories.
        branch: Optional branch to clone when `source` is a git URL.
    """
    exit_code = sync_logic(source, token, branch)
    ctx.exit(exit_code)
