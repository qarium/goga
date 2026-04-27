from __future__ import annotations

import click


@click.command()
@click.argument("cells", nargs=-1)
@click.option("--lang", default="python")
@click.pass_context
def compare(ctx: click.Context, cells: tuple[str, ...], lang: str) -> None:
    """Compare CODEMANIFEST contract with implementation."""
