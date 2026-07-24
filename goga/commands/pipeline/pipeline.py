from __future__ import annotations

from pathlib import Path

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
@click.option(
    "--proxy",
    type=str,
    default=None,
    help="HTTP/HTTPS proxy URL; overrides config.pipeline.proxy",
)
@click.option(
    "--add-host",
    "add_host",
    multiple=True,
    help="Add a docker run --add-host HOST:IP entry; merges on top of config.pipeline.hosts",
)
@click.option(
    "--clean",
    "clean",
    is_flag=True,
    default=False,
    help="Wipe the persistent afm state directory before launch (run mode only)",
)
@click.option(
    "--update",
    "-u",
    "update",
    is_flag=True,
    default=False,
    help="Pull the image before launching the container",
)
@click.option(
    "--workflow",
    type=str,
    default=None,
    help="Apply an explicit workflow at .goga/workflows/<name>.yml (file must exist)",
)
@click.option(
    "--no-workflow",
    "no_workflow",
    is_flag=True,
    default=False,
    help="Disable workflow application entirely (sets GOGA_WORKFLOW_DISABLED=1 in-container)",
)
@click.pass_context
def pipeline(  # noqa: PLR0913, PLR0917
    ctx: click.Context,
    name: str | None,
    extra_env: tuple[str, ...],
    proxy: str | None,
    add_host: tuple[str, ...],
    clean: bool,
    update: bool,
    workflow: str | None,
    no_workflow: bool,
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
        proxy: optional HTTP/HTTPS proxy URL from ``--proxy``. When None, falls
            back to ``config.pipeline.proxy``. The resolved value (CLI wins over
            config) drives HTTP_PROXY/HTTPS_PROXY/NO_PROXY in the container
            env-file.
        add_host: raw ``HOST:IP`` strings from the repeatable ``--add-host``
            option (empty tuple when absent). Merged on top of
            ``config.pipeline.hosts``; CLI wins on key conflict. Forwarded to
            ``run_pipeline_container`` as a resolved hosts dict.
        clean: flag from ``--clean``. Run mode only — when True,
            ``run_pipeline_container`` wipes the persistent afm state directory
            before launch. Ignored in discovery mode.
        update: flag from ``--update/-u``. When True, pull the image before
            launching the container. Available in both modes.
        workflow: optional workflow name from ``--workflow NAME`` (without the
            ``.yml`` extension). When provided, an explicit workflow is requested
            — the launcher validates that ``<cwd>/.goga/workflows/<workflow>.yml``
            exists BEFORE launching the container (clean ``ClickException``,
            exit 1 on a missing file). Mutually exclusive with ``no_workflow``.
        no_workflow: flag from ``--no-workflow``. When True, the launcher forces
            the in-container pipeline to skip workflow resolution entirely (writes
            ``GOGA_WORKFLOW_DISABLED=1`` into the env-file). Mutually exclusive
            with ``workflow``. Performs NO host-side validation — it is a pure
            flag forwarded into the container.

    Raises:
        click.ClickException: When ``.goga/config.yml`` cannot be loaded, when
            the ``pipeline`` section is absent (the section is required to run a
            pipeline), when ``--workflow`` and ``--no-workflow`` are both set
            (mutually exclusive), or when an explicit ``--workflow NAME`` names a
            file that does not exist at ``<cwd>/.goga/workflows/<name>.yml``.
    """
    try:
        config = load_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    # Step 1b — host-side None-guard: the pipeline section is optional at the
    # loader level (load_config returns config.pipeline=None when absent), but
    # `goga pipeline` cannot run without it. Raise a clean ClickException BEFORE
    # any config.pipeline.* access and BEFORE dispatch into
    # run_pipeline_container, so a pipeline-less config surfaces as a clean
    # message + exit 1 in both discovery and run modes rather than an
    # AttributeError. This also covers run_pipeline_container transitively — it
    # is only reachable through this command, so a single check here is enough.
    if config.pipeline is None:
        raise click.ClickException("pipeline section is required in .goga/config.yml to run 'goga pipeline'")

    # Resolve the proxy: the --proxy CLI value wins over config.pipeline.proxy.
    resolved_proxy = proxy if proxy is not None else config.pipeline.proxy

    # Resolve hosts: merge config.pipeline.hosts with parsed --add-host entries.
    # Each "HOST:IP" string is split on the first colon; CLI entries override
    # config entries on host-key conflict. Format is not validated beyond the
    # split — Docker reports malformed entries itself.
    merged_hosts: dict[str, str] = {**config.pipeline.hosts}
    for entry in add_host:
        host, _, ip = entry.partition(":")
        merged_hosts[host] = ip

    # Step 5 — workflow flag combination: --workflow and --no-workflow are
    # mutually exclusive. Verified BEFORE the host-side existence check and
    # BEFORE container launch so a contradictory CLI surface exits 1 with a
    # readable message rather than reaching docker. This runs after
    # load_config / pipeline-section / proxy / hosts resolution but always
    # before dispatch — no docker side effects can precede it.
    if workflow is not None and no_workflow:
        raise click.ClickException("--workflow and --no-workflow are mutually exclusive")

    # Step 6 — host-side existence validation for an explicit --workflow. The
    # basename auto-match (no flags) and --no-workflow alone perform NO
    # host-side validation: both are resolved in-container by the run_pipeline
    # routine. Only an explicit --workflow <name> is validated here so a typo
    # surfaces as a clean message + exit 1 BEFORE the container is launched.
    # Workflow paths are project-only — resolved from Path.cwd() (which is
    # /workspace in-container), mirroring the in-container resolution. A name
    # that escapes the workflows dir (``..`` segment or absolute prefix) is
    # rejected as exit 1 — never resolved into the wider filesystem.
    if workflow is not None:
        workflows_root = (Path.cwd() / ".goga" / "workflows").resolve()
        workflow_path = workflows_root / f"{workflow}.yml"
        try:
            workflow_path.resolve().relative_to(workflows_root)
        except ValueError:
            raise click.ClickException(f"invalid workflow name {workflow!r}") from None
        if not workflow_path.exists():
            raise click.ClickException(f"workflow '{workflow}' not found at {workflow_path}")

    # Dispatch with explicit keyword arguments so the click surface — and its
    # tests — can assert on each argument by name rather than by position.
    # In discovery mode (name is None) clean is a no-op, so it is forced to
    # False regardless of the CLI flag. The workflow flags are forwarded
    # unconditionally — run_pipeline_container decides per mode (discovery is a
    # no-op for the workflow layer; run mode writes the env-file entries).
    exit_code = run_pipeline_container(
        name=name,
        config=config,
        extra_env=extra_env,
        proxy=resolved_proxy,
        hosts=merged_hosts,
        clean=clean if name is not None else False,
        update=update,
        workflow=workflow,
        no_workflow=no_workflow,
    )
    ctx.exit(exit_code)
