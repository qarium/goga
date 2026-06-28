from __future__ import annotations

from pathlib import Path

import click

from ...afm import Source, list_flows, run_flow


@click.group()
def flow() -> None:
    """Manage goga flows (list and run via external flowmanager)."""


@flow.command(name="ls")
def ls() -> None:
    """List available goga flows.

    Resolves the project and user source directories from the current working
    directory and the user home, delegates discovery to
    :func:`goga.afm.list_flows`, and echoes one flow per line. Project flows are
    annotated with ``(project)``; user flows are echoed bare.

    This command only reads the local filesystem — it never invokes the
    ``flowmanager`` binary.
    """
    project_dir = Path.cwd() / ".goga" / "flows"
    user_dir = Path.home() / ".goga" / "flows"
    entries = list_flows(project_dir, user_dir)
    for entry in entries:
        if entry.source == Source.PROJECT:
            click.echo(f"{entry.name} (project)")
        else:
            click.echo(entry.name)


@flow.command(name="run")
@click.argument("name")
@click.pass_context
def run(ctx: click.Context, name: str) -> None:
    """Run a goga flow by name via external flowmanager.

    Resolves the project and user source directories from the current working
    directory and the user home and delegates execution to
    :func:`goga.afm.run_flow`, which invokes ``flowmanager run`` with the flow's
    absolute path. The resulting exit code is propagated via ``ctx.exit``.

    Args:
        ctx: Click execution context used to propagate the exit code.
        name: flow name without extension (e.g. ``"deploy"``).
    """
    project_dir = Path.cwd() / ".goga" / "flows"
    user_dir = Path.home() / ".goga" / "flows"
    exit_code = run_flow(name, project_dir, user_dir)
    ctx.exit(exit_code)
