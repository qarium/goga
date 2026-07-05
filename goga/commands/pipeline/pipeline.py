from __future__ import annotations

import click
import yaml

from ...config import load_config
from .run_pipeline_container import run_pipeline_container


@click.command()
@click.argument("name", required=False)
@click.option(
    "-e",
    "--env",
    "extra_env",
    multiple=True,
    help="Pass env var to container (KEY=VALUE). Effective only in run mode.",
)
@click.pass_context
def pipeline(
    ctx: click.Context,
    name: str | None,
    extra_env: tuple[str, ...],
) -> None:
    """Run a goga pipeline by name, or list available pipelines when no name is given.

    Both modes launch the goga Docker container and delegate to
    ``run_pipeline_container`` — discovery and run are in-container only. The host
    never reads pipeline files directly.

    Without ``name`` (discovery mode): the container prints the
    ``Available pipelines:`` header followed by one pipeline per line.

    With ``name`` (run mode): the container runs the named pipeline via the
    external ``afm`` binary. The container's exit code is propagated via
    ``ctx.exit``.

    Args:
        ctx: Click execution context used to propagate the exit code.
        name: pipeline name without extension (e.g. ``"deploy"``). When ``None``
            selects discovery mode.
        extra_env: additional ``KEY=VALUE`` strings forwarded into the container
            env-file in run mode (e.g. an agent authorization token). Ineffective
            in discovery mode, which never writes an env-file.

    Raises:
        click.ClickException: When ``.goga/config.yml`` cannot be loaded.
    """
    try:
        config = load_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    # Dispatch with explicit keyword arguments so the click surface — and its
    # tests — can assert on each argument by name rather than by position.
    exit_code = run_pipeline_container(name=name, config=config, extra_env=extra_env)
    ctx.exit(exit_code)
