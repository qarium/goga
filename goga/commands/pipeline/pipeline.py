from __future__ import annotations

from pathlib import Path

import click

from ...pipeline import PipelineSource, list_pipelines, run_pipeline


@click.command()
@click.argument("name", required=False)
@click.pass_context
def pipeline(ctx: click.Context, name: str | None) -> None:
    """Run a goga pipeline by name, or list available pipelines when no name is given.

    Without ``name`` (discovery mode): prints the ``Available pipelines:`` header
    followed by one pipeline per line. Project pipelines are annotated with
    ``(project)``; user pipelines are echoed bare. Read-only — does not invoke
    ``flowmanager``.

    With ``name`` (run mode): runs the named pipeline via the external
    ``flowmanager`` binary through :func:`goga.pipeline.run_pipeline`. The
    ``flowmanager`` exit code is propagated via ``ctx.exit``.

    Args:
        ctx: Click execution context used to propagate the exit code.
        name: pipeline name without extension (e.g. ``"deploy"``). The ``.yml``
            extension is added internally during path resolution.
    """
    project_dir = Path.cwd() / ".goga" / "pipelines"
    user_dir = Path.home() / ".goga" / "pipelines"

    if name is None:
        click.echo("Available pipelines:")
        for entry in list_pipelines(project_dir, user_dir):
            if entry.source == PipelineSource.PROJECT:
                click.echo(f"  {entry.name} (project)")
            else:
                click.echo(f"  {entry.name}")
        ctx.exit(0)

    ctx.exit(run_pipeline(name, project_dir, user_dir))
