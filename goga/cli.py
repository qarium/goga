from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import click

from .commands import (
    build,
    config,
    connect,
    contract,
    history,
    hooks,
    init,
    install,
    lint,
    pipeline,
    schema,
    tool,
    topics,
    uninstall,
    upgrade,
    usages,
)
from .version import host_goga_version

# Clean-error message of the --version flag (see _print_version): the metadata
# failure is surfaced as a ClickException — stderr "Error: ...", exit code 1,
# no traceback.
MSG_CLI_VERSION_FAILED = "cannot determine the installed goga version ({exc})"


def _print_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Print the bare host goga version and exit (eager --version/-v callback)."""
    if not value or ctx.resilient_parsing:
        return

    try:
        click.echo(host_goga_version())
        ctx.exit(0)
    except PackageNotFoundError as exc:
        raise click.ClickException(MSG_CLI_VERSION_FAILED.format(exc=exc)) from exc


@click.group()
@click.option(
    "--version",
    "-v",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_version,
    help="Show the host goga version and exit.",
)
def app() -> None:
    """Goga — CLI tool suite for CODEMANIFEST-based development."""


app.add_command(build)
app.add_command(config)
app.add_command(connect)
app.add_command(init)
app.add_command(install)
app.add_command(uninstall)
app.add_command(lint)
app.add_command(schema)
app.add_command(contract)
app.add_command(pipeline)
app.add_command(usages)
app.add_command(tool)
app.add_command(upgrade)
app.add_command(history)
app.add_command(hooks)
app.add_command(topics)
