from __future__ import annotations

import click

from .commands import build, config, connect, contract, flow, init, lint, schema, sync, tool, upgrade


@click.group()
def app() -> None:
    """Goga — CLI tool suite for CODEMANIFEST-based development."""


app.add_command(build)
app.add_command(config)
app.add_command(connect)
app.add_command(init)
app.add_command(lint)
app.add_command(schema)
app.add_command(contract)
app.add_command(flow)
app.add_command(sync)
app.add_command(tool)
app.add_command(upgrade)
