from __future__ import annotations

import click

from .commands import build, init, linter, schema


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(build)
app.add_command(init)
app.add_command(linter)
app.add_command(schema)
