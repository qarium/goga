from __future__ import annotations

import click

from .commands import linter


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(linter)
