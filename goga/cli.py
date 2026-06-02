from __future__ import annotations

import click

from .commands import build, config, connect, contract, linter, schema, sync, tool


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(build)
app.add_command(config)
app.add_command(connect)
app.add_command(linter)
app.add_command(schema)
app.add_command(contract)
app.add_command(sync)
app.add_command(tool)
