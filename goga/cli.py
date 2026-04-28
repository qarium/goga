from __future__ import annotations

import click

from .commands import build, contract, install, linter, schema


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(build)
app.add_command(install)
app.add_command(linter)
app.add_command(schema)
app.add_command(contract)
