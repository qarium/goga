from __future__ import annotations

from pathlib import Path

import click
import yaml

from ...config import load_project_config
from ...config.hooks import ConfigHooks
from ...docker import is_in_docker
from ...pipeline.workflow import load_home_profiles
from ...topics import ensure_topic
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
    "-t",
    "--topic",
    "topic",
    type=str,
    default=None,
    help="Bring the repository onto the requested work before the run, "
    "creating it when nothing hosts it (branch name, topic slug, or prefix; "
    "run form only)",
)
@click.option(
    "--todo",
    "todo",
    is_flag=True,
    default=False,
    help="Open the editor with the topic's todo.md after the switch or fast creation (run form only; requires --topic)",
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
    help="Disable workflow application entirely (run and card forms)",
)
@click.option(
    "-p",
    "--profile",
    "profile",
    type=str,
    default=None,
    help="Activate a contributor profile from .goga/profiles/ or ~/.goga/profiles (run and card forms)",
)
@click.option(
    "-s",
    "--skip",
    "skip",
    multiple=True,
    help="Exclude a stage from the compiled pipeline (run and card forms; repeatable)",
)
@click.option(
    "--parallel",
    "parallel",
    type=int,
    default=None,
    help="cap concurrently executing stages (run mode only; threads to afm --max-parallel)",
)
@click.option(
    "--fail-on-error",
    "fail_on_error",
    is_flag=True,
    default=False,
    help="exit non-zero when a stage fails (run mode only; threads to afm --exit-on-fail)",
)
@click.pass_context
def pipeline(  # noqa: C901, PLR0912, PLR0913, PLR0915, PLR0917
    ctx: click.Context,
    name: str | None,
    list_requested: bool,
    info: bool,
    topic: str | None,
    todo: bool,
    extra_env: tuple[str, ...],
    proxy: str | None,
    add_host: tuple[str, ...],
    clean: bool,
    update: bool,
    workflow: str | None,
    no_workflow: bool,
    profile: str | None,
    skip: tuple[str, ...],
    parallel: int | None,
    fail_on_error: bool = False,
) -> None:
    """Run a goga pipeline, or inspect the available ones.

    Without flags beyond NAME: runs the named pipeline inside the goga Docker
    container and propagates its exit code.

    With -l/--list: prints the available pipelines; add -i/--info for a
    one-line description of each.

    With NAME and -i/--info: prints the pipeline card (name, description,
    stages in execution order) without running anything.

    With -t/--topic: bring the repository onto the requested work (a branch
    name, a topic slug, or their prefix) before the run — creating it when
    nothing hosts the identifier. With --todo: open the editor with the
    topic's todo.md after the switch or the fast creation (run form only;
    requires --topic).

    All forms launch the goga Docker container and delegate there — the host
    never reads pipeline files directly. Inside the goga container itself
    (the GOGA_DOCKER=1 marker) every form instead executes the SAME composed
    in-container command directly as a child process; the host-only options
    (-t/--topic, --todo, -u/--update, -e/--env, --add-host, --proxy) are
    rejected there with an error naming the option before any other work —
    they configure the docker launch, which does not exist in-container.
    """
    try:
        authored = load_project_config()
        # The config-amendment checkpoint joins the load inside the try: a
        # hard checkpoint failure is the same clean error as a failed load.
        overlay = ConfigHooks().amend_config(config=authored)
    except (FileNotFoundError, KeyError, ValueError, ImportError, yaml.YAMLError) as exc:
        # ImportError — a broken tool package facade during the registry
        # build — is the same clean error, never a raw traceback.
        raise click.ClickException(str(exc)) from exc

    for line in overlay.summary_lines:
        click.echo(line, err=True)

    # Every downstream read addresses the effective configuration.
    config = overlay.config

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
    # `client.command`). No host-side guard here, and no behavioral read of
    # pipeline.agent or pipeline.env anywhere in this cell: the in-container
    # run coordination resolves the agent into the afm configuration file it
    # authors and applies pipeline.env as the afm launch env layer, letting
    # per-stage workflow agents (or afm's own defaults) cover an absent agent.

    # Step 1a — resolve the execution substrate once; on the direct path
    # (inside the goga image, the GOGA_DOCKER marker) reject every host-only
    # option BEFORE any other work — no topic procedure, no form validation
    # side effects, no port allocation, no launch. Each option configures the
    # docker launch, which does not exist inside the container; nothing is
    # silently ignored. The host path (marker absent) skips this step
    # entirely.
    direct = is_in_docker()

    if direct:
        host_only = [
            ("--topic/-t", topic is not None),
            ("--todo", todo),
            ("--update/-u", update),
            ("--env/-e", bool(extra_env)),
            ("--add-host", bool(add_host)),
            ("--proxy", proxy is not None),
        ]

        for flag, passed in host_only:
            if passed:
                raise click.ClickException(
                    f"{flag} is host-only: it configures the docker launch, "
                    f"which does not exist inside the goga container"
                )

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

    # Step 2.5 — leading-dash argv tokens. Click consumes any next token as
    # an option value, so `-s --no-workflow` parses on the host with the flag
    # swallowed as the skip name — but the in-container argparse parser
    # classifies a leading-dash token as an option, and the composed argv
    # (``["-s", "--no-workflow"]``) dies there as ``expected one argument``
    # only AFTER the whole launch ceremony. The same holds for a dash-leading
    # pipeline name (``goga pipeline -- -weird``): the container parser reads
    # the name as an option and reports the missing positional. Reject both
    # forms here, before any docker activity. This is argv-form parsability,
    # not stage-name validation: a non-dash skip name stays forwarded as
    # parsed, unknown or not. The -w check acts wherever the flag is passed —
    # step 2.4's validation does — while the name and -s checks act only in
    # the run and card forms, the forms whose launchers carry them; the
    # listing forms silently ignore -s. The profile value joins the same
    # guard wherever the flag is passed.
    if workflow is not None and workflow.startswith("-"):
        raise click.ClickException(f"invalid workflow name {workflow!r}")

    if profile is not None and profile.startswith("-"):
        raise click.ClickException(f"invalid profile name {profile!r}")

    if name is not None:
        if name.startswith("-"):
            raise click.ClickException(f"invalid pipeline name {name!r}")

        for skip_name in skip:
            if skip_name.startswith("-"):
                raise click.ClickException(f"invalid skip name {skip_name!r}")

    # Step 3 — topic procedure (run form only: `name` given, no --list, no
    # --info). Every git action happens here on the host, AFTER every step-2
    # form check and BEFORE any docker activity — a form error or a topic
    # error never refreshes, builds, or launches an image. `--todo` without
    # `-t/--topic` is a clean error here: the entry needs requested work, and
    # the abort precedes any git or docker activity. The flat list, overview,
    # and card forms skip the procedure silently: passing -t or --todo there
    # is not an error and has no effect. The single result line of
    # `ensure_topic` (a switch, a fresh branch created from a remote-tracking
    # ref, the already-on-host confirmation, or the creation of fresh work —
    # branch plus topic directory — when nothing hosts the identifier) is
    # echoed to stdout exactly once, immediately after the procedure and
    # before the dispatch — and never forwarded into a launcher: the container
    # sees the branch through the mounted project. Under --todo the external
    # editor opens with the topic's todo.md inside the domain orchestration —
    # after the switch or the fast creation, and only on an interactive
    # terminal (the domain aborts cleanly otherwise, still before any docker
    # activity).
    if name is not None and not list_requested and not info:
        if todo and topic is None:
            raise click.ClickException("--todo acts only together with --topic")
        if topic is not None:
            line = ensure_topic(topic, todo)
            click.echo(line)

    # Step 4 — home bundle (the contributor-profile carriage, host half): load
    # ~/.goga/profiles/ once via `load_home_profiles` — after every
    # argument-form check and before the dispatch, so a malformed home profile
    # is one clean error BEFORE any docker activity (no image refresh, no
    # first-run build, no launch). The bundle is handed to both launchers,
    # which own the env-file carriage; an empty bundle normalizes to None per
    # the carriage contract, and the payload content never appears in any
    # message.
    try:
        home_profiles = load_home_profiles(Path.home() / ".goga" / "profiles")
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    home_bundle = home_profiles or None

    # Step 5 — dispatch. The info forms receive hosts from the config ONLY:
    # --add-host is a run-form surface (an info container is read-only, so
    # extra host aliases there would be dead weight) and is a deliberate no-op.
    info_hosts: dict[str, str] = {**config.pipeline.hosts}

    if list_requested:
        # Flat list or overview — the listing subcommand in-container. The
        # workflow decision and the profile value name no composition there;
        # the bundle still travels (the launcher owns the cargo rule).
        exit_code = run_pipeline_info_container(
            name=None,
            info=info,
            config=config,
            hosts=info_hosts,
            update=update,
            workflow=None,
            no_workflow=False,
            profile=None,
            home_profiles=home_bundle,
        )
    elif info:
        # Card form — NAME --info with the workflow decision, the profile
        # value, and the skip names forwarded as given: the same flags produce
        # the same composition in card and run forms.
        exit_code = run_pipeline_info_container(
            name=name,
            info=True,
            config=config,
            hosts=info_hosts,
            update=update,
            workflow=workflow,
            no_workflow=no_workflow,
            profile=profile,
            skip=skip,
            home_profiles=home_bundle,
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
        # position. clean is run-form state; --clean never deletes
        # anything in the info forms (they dispatch above). The profile value
        # and the home bundle join the full argument set — the launcher owns
        # their carriage (the --profile argv token and the env-file lines).
        # The fail-fast decision joins the run form only — the listing and
        # card dispatches above accept --fail-on-error without effect.
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
            profile=profile,
            skip=skip,
            parallel=parallel,
            home_profiles=home_bundle,
            fail_on_error=fail_on_error,
        )

    ctx.exit(exit_code)
