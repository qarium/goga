from __future__ import annotations

from pathlib import Path

import click
import yaml

from ...config import load_project_config
from .branch import ensure_pipeline_branch
from .run_pipeline_container import run_pipeline_container
from .run_pipeline_info_container import run_pipeline_info_container


@click.command()
@click.argument("name", required=False)
@click.option(
    "-l",
    "--list",
    "list_requested",
    is_flag=True,
    default=False,
    help="List available pipelines (add --info for a one-line description each)",
)
@click.option(
    "-i",
    "--info",
    "info",
    is_flag=True,
    default=False,
    help="Show pipeline descriptions (--list) or a pipeline card (NAME) instead of running",
)
@click.option(
    "-b",
    "--branch",
    "branch",
    type=str,
    default=None,
    help="Create and switch to a fresh branch before the run (run form only)",
)
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
    help="Add a docker run --add-host HOST:IP entry; merges on top of config.pipeline.hosts (run mode only)",
)
@click.option(
    "-c",
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
    help="Pull the image before launching the container (run and --list forms; no-op with --info)",
)
@click.option(
    "--workflow",
    "-w",
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
@click.option(
    "-s",
    "--skip",
    "skip",
    multiple=True,
    help="Exclude a stage from the compiled pipeline (run mode only; repeatable); forwarded as GOGA_SKIP_STAGES",
)
@click.option(
    "-p",
    "--parallel",
    "parallel",
    type=int,
    default=None,
    help="cap concurrently executing stages (run mode only; threads to afm --max-parallel)",
)
@click.pass_context
def pipeline(  # noqa: C901, PLR0912, PLR0913, PLR0917
    ctx: click.Context,
    name: str | None,
    list_requested: bool,
    info: bool,
    branch: str | None,
    extra_env: tuple[str, ...],
    proxy: str | None,
    add_host: tuple[str, ...],
    clean: bool,
    update: bool,
    workflow: str | None,
    no_workflow: bool,
    skip: tuple[str, ...],
    parallel: int | None,
) -> None:
    """Run a goga pipeline, or inspect the available ones.

    Without flags beyond NAME: runs the named pipeline inside the goga Docker
    container and propagates its exit code.

    With -l/--list: prints the available pipelines; add -i/--info for a
    one-line description of each.

    With NAME and -i/--info: prints the pipeline card (name, description,
    stages in execution order) without running anything.

    With -b/--branch: prepare a fresh git branch and history topic before the run.

    All forms launch the goga Docker container and delegate there — the host
    never reads pipeline files directly.
    """
    try:
        config = load_project_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    # Step 1.1 — host-side None-guard: the pipeline section is optional at the
    # loader level (load_project_config returns config.pipeline=None when absent), but
    # `goga pipeline` cannot run without it. Raise a clean ClickException BEFORE
    # any config.pipeline.* access and BEFORE dispatch into either launcher, so a
    # pipeline-less config surfaces as a clean message + exit 1 in every form
    # rather than an AttributeError. This also covers both launchers
    # transitively — they are only reachable through this command, so a single
    # check here is enough.
    if config.pipeline is None:
        raise click.ClickException("pipeline section is required in .goga/config.yml to run 'goga pipeline'")

    # pipeline.agent is OPTIONAL: it is None at the loader level when absent/
    # empty, and that is a valid state — the agent may be supplied per-stage by
    # the workflow (composed into each stage's `command:` override by the
    # compiler; afm ≥0.4.15 honors per-stage commands over the global
    # `client.command`). No host-side guard here: run_pipeline_container writes
    # the afm-config `client.command` only when an agent is present, and lets
    # per-stage workflow agents (or afm's own defaults) cover its absence.

    # Step 2 — form validation, BEFORE any docker activity (no image refresh,
    # no first-run build, no container launch can precede a form error). The
    # checks are ordered 2.1 → 2.4 and act in EVERY form.

    # Step 2.1 — --list addresses the listing subcommand; a positional name
    # addresses the card/run subcommand. Both at once is a contradiction.
    if list_requested and name is not None:
        raise click.ClickException("--list and a pipeline name are mutually exclusive")

    # Step 2.2 — a bare `goga pipeline` names no form at all.
    if name is None and not list_requested:
        raise click.ClickException(
            'Missing pipeline name. Use "goga pipeline --list" to list available pipelines, or provide a pipeline name.'
        )

    # Step 2.3 — workflow flag combination: --workflow and --no-workflow are
    # mutually exclusive. Verified BEFORE the existence check and BEFORE
    # dispatch so a contradictory CLI surface exits 1 with a readable message
    # rather than reaching docker. This fires regardless of whether the named
    # workflow file exists.
    if workflow is not None and no_workflow:
        raise click.ClickException("--workflow and --no-workflow are mutually exclusive")

    # Step 2.4 — host-side existence validation for an explicit --workflow. The
    # basename auto-match (no flags) and --no-workflow alone perform NO
    # host-side validation: both are resolved in-container. Only an explicit
    # --workflow <name> is validated here so a typo surfaces as a clean message
    # + exit 1 BEFORE the container is launched — in every form (run and card).
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

    # Step 3 — branch procedure (run form only: `name` given, no --list, no
    # --info, and -b/--branch given). Every git action happens here on the
    # host, AFTER every step-2 form check and BEFORE any docker activity — a
    # form error or a branch error never refreshes, builds, or launches an
    # image. The flat list, overview, and card forms skip the procedure
    # silently: passing -b there is not an error and has no effect. The final
    # branch name (the created-and-switched one, or the current one in the
    # already-on-branch case) is echoed to stdout exactly once, immediately
    # after the procedure and before the dispatch — and never forwarded into
    # a launcher: the container sees the branch through the mounted project.
    if branch is not None and name is not None and not list_requested and not info:
        final_branch = ensure_pipeline_branch(branch)
        click.echo(f"Pipeline running on branch {final_branch}")

    # Step 4 — dispatch. The info forms receive hosts from the config ONLY:
    # --add-host is a run-form surface (an info container is read-only, so
    # extra host aliases there would be dead weight) and is a deliberate no-op.
    info_hosts: dict[str, str] = {**config.pipeline.hosts}

    if list_requested:
        # Flat list or overview — the listing subcommand in-container.
        exit_code = run_pipeline_info_container(
            name=None,
            info=info,
            config=config,
            hosts=info_hosts,
            update=update,
            workflow=None,
            no_workflow=False,
        )
    elif info:
        # Card form — NAME --info with the workflow decision forwarded as given.
        exit_code = run_pipeline_info_container(
            name=name,
            info=True,
            config=config,
            hosts=info_hosts,
            update=update,
            workflow=workflow,
            no_workflow=no_workflow,
        )
    else:
        # Run form. Resolve the proxy: the --proxy CLI value wins over
        # config.pipeline.proxy. Resolve hosts: merge config.pipeline.hosts
        # with parsed --add-host entries. Each "HOST:IP" string is split on
        # the first colon; CLI entries override config entries on host-key
        # conflict. Format is not validated beyond the split — Docker reports
        # malformed entries itself.
        resolved_proxy = proxy if proxy is not None else config.pipeline.proxy
        merged_hosts: dict[str, str] = {**config.pipeline.hosts}

        for entry in add_host:
            host, _, ip = entry.partition(":")
            merged_hosts[host] = ip

        # Dispatch with explicit keyword arguments so the click surface — and
        # its tests — can assert on each argument by name rather than by
        # position. clean/skip are run-form state; --clean never deletes
        # anything in the info forms (they dispatch above).
        exit_code = run_pipeline_container(
            name=name,
            config=config,
            extra_env=extra_env,
            proxy=resolved_proxy,
            hosts=merged_hosts,
            clean=clean,
            update=update,
            workflow=workflow,
            no_workflow=no_workflow,
            skip=skip,
            parallel=parallel,
        )
    ctx.exit(exit_code)
