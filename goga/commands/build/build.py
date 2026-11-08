from __future__ import annotations

import contextlib
import logging
import os
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import click
import yaml

from ...config import HomeConfig, load_home_config, load_project_config
from ...config.hooks import ConfigHooks
from ...docker import (
    DockerRunner,
    docker_build_if_not_exist,
    docker_update,
    encode_extra_env,
    is_in_docker,
    profile_carriage_lines,
    run_direct,
    translate_params,
)
from ...pipeline.workflow import load_home_profiles
from ...runtime import resolve_runtime_dir

logger = logging.getLogger(__name__)


def _check_docker() -> bool:
    """Check whether the docker CLI is available on PATH.

    Returns:
        True if `docker --version` exits successfully, False otherwise.
    """
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, PermissionError, OSError):
        return False


def _read_git_config() -> dict[str, str]:
    """Read git author/committer identity from the local git config.

    Returns:
        A dict of git identity environment variables, or an empty dict when
        git is unavailable or name/email are not configured.
    """
    try:
        name_result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            check=False,
        )
        email_result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, PermissionError, OSError):
        return {}

    name = name_result.stdout.strip()
    email = email_result.stdout.strip()
    if not name or not email:
        return {}

    return {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }


def _write_env_file(lines: list[str]) -> Path:
    """Write environment lines to a private temporary env file created with mode 0600.

    Args:
        lines: The fully assembled KEY=VALUE lines of the container env-file,
            in ladder order (the ``GOGA_EXTRA_ENV`` payload line, then the
            profile engine lines when they carry cargo).

    Returns:
        Path to the written temporary file.
    """
    fd, path = tempfile.mkstemp(prefix="goga-env-")

    with os.fdopen(fd, "w") as f:
        Path(path).chmod(stat.S_IRUSR | stat.S_IWUSR)

        for line in lines:
            f.write(f"{line}\n")

    return Path(path)


def _compose_env_lines(
    home_env: dict[str, str],
    git_env: dict[str, str],
    extra_env: tuple[str, ...],
    proxy: str | None,
    home_profiles: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Compose the container env lines (Algorithm step 7) — environment layers only.

    The single composition shared by both execution substrates (one
    composition, two sinks — per ``direct-runner``): the host path writes the
    lines into the private env-file consumed by ``docker run --env-file``; the
    direct path parses them into the child env layer of ``run_direct``.

    Args:
        home_env: ``home.env`` from the machine-wide home config — the
            lowest-priority env layer (git identity and CLI win on key
            conflict). Survives where unconflicted.
        git_env: Git identity variables from ``_read_git_config`` — layered
            over ``home_env`` (an absent git config contributes nothing).
        extra_env: Additional raw KEY=VALUE strings written verbatim (a
            SEPARATE channel above the dict layers, winning on key conflict)
            and encoded into the payload line from the same values.
        proxy: Resolved HTTP/HTTPS proxy URL (CLI wins over config in the
            caller); populates the proxy triple when non-None.
        home_profiles: The loaded home bundle (the ``load_home_profiles``
            result of the caller) — encoded into the ``GOGA_HOME_PROFILES``
            engine line only when non-empty (per ``home-profiles-carriage``);
            the payload never appears in any message.

    Returns:
        The fully assembled KEY=VALUE lines in ladder order (the
        ``GOGA_EXTRA_ENV`` payload line before the two profile-carriage
        engine lines).

    Note:
        Ladder order (lowest to highest): the ``home_env`` base under git
        identity, the raw ``extra_env`` lines, the engine proxy triple when a
        proxy resolved, the ``GOGA_EXTRA_ENV`` payload line, then the two
        profile-carriage engine lines (``GOGA_PROFILE`` — the ambient host
        value, only when non-empty — and ``GOGA_HOME_PROFILES``, only when the
        bundle is non-empty). The engine lines follow the CLI lines and SKIP a
        key the CLI explicitly supplied — the raw CLI line keeps winning
        without a duplicate launcher line (the documented
        ``-e HTTP_PROXY=...`` escape hatch). ``GOGA_WORKFLOW`` is NEVER
        written by this launcher (the pipeline-run launcher owns it); the task
        env layer (``build.env``) NEVER enters the lines — it reaches the
        container through the mounted ``.goga/config.yml`` and applies
        in-container at the pass launches.
    """
    # home.env is the BASE layer — lowest priority; git identity overrides it.
    # The CLI raw channel and the engine lines are appended after the base
    # lines, so they still win on key conflict.
    lines = [f"{key}={value}" for key, value in {**home_env, **git_env}.items()]
    lines += list(extra_env)

    # Engine lines — the proxy triple only in the build domain (NO_PROXY is
    # fixed at localhost,127.0.0.1, there is no --no-proxy) — are written after
    # the CLI lines so the env-file itself respects the ladder; a key the CLI
    # explicitly supplied is SKIPPED, keeping the documented -e escape hatch
    # winning under docker's last-write-wins.
    cli_keys = {pair.partition("=")[0] for pair in extra_env if "=" in pair}
    engine: dict[str, str] = {}

    if proxy is not None:
        engine |= {
            "HTTP_PROXY": proxy,
            "HTTPS_PROXY": proxy,
            "NO_PROXY": "localhost,127.0.0.1",
        }

    engine = {key: value for key, value in engine.items() if key not in cli_keys}
    lines += [f"{key}={value}" for key, value in engine.items()]

    # The payload line — the second carrier composed from the SAME parsed CLI
    # values as the raw lines above (one source, two carriers per
    # extra-env-carriage).
    lines.append(f"GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}")

    # The contributor-profile carriage — two engine lines after the payload
    # line, composed by the shared `profile_carriage_lines` helper (same
    # engine-skip rule: an explicit -e key keeps winning; each line written
    # only when it carries cargo). GOGA_WORKFLOW is NEVER written by this
    # launcher (the pipeline-run launcher owns it); the payload values never
    # appear in any message.
    lines += profile_carriage_lines(os.environ.get("GOGA_PROFILE", ""), home_profiles, None, cli_keys)

    return lines


def _env_overlay(lines: list[str]) -> dict[str, str]:
    """Parse env-file lines into the direct-substrate child env layer.

    Args:
        lines: The ``_compose_env_lines`` result — KEY=VALUE lines in ladder
            order.

    Returns:
        The parsed mapping — each line split on the FIRST ``=``, applied in
        order so a later line of the same key wins, mirroring the
        ``docker run --env-file`` last-write-wins semantics the host path
        relies on.
    """
    return dict(line.split("=", 1) for line in lines)


def _cli_flags_to_args(cli_flags: dict[str, bool | str | int | None]) -> list[str]:
    """Render the build cli_flags map into trailing goga.build argument list.

    Args:
        cli_flags: Build flags forwarded to the in-container entrypoint.

    Returns:
        A flat list of CLI argument tokens (e.g. ``["--dry-run", "--wait", "5m"]``).
    """
    args: list[str] = []

    if cli_flags.get("dry_run"):
        args.append("--dry-run")
    if cli_flags.get("skip_manifest_check"):
        args.append("--skip-manifest-check")

    # Tri-state review pair: True → --skip-review, False → --no-skip-review,
    # None → neither (the in-container build resolves None against the config).
    sr = cli_flags.get("skip_review")

    if sr is True:
        args.append("--skip-review")
    elif sr is False:
        args.append("--no-skip-review")

    for flag in (
        "session_timeout",
        "idle_timeout",
        "wait",
        "max_iterations",
        "review_patience",
        "base_ref",
        "workflow",
        "profile",
    ):
        val = cli_flags.get(flag)
        if val is not None:
            args.extend([f"--{flag.replace('_', '-')}", str(val)])

    return args


def resolve_build_runtime_dir() -> Path:
    """Compute the host-side ralphex runtime directory for this build.

    Returns:
        The absolute host path
        ``~/.goga/runtime/builds/<normalized_project>/<branch>/`` that the
        build command bind-mounts into the container at
        ``/workspace/.ralphex`` so ralphex state never touches the user's
        project directory. Pure with respect to the filesystem — the
        directory is NOT created here (creation is the caller's
        responsibility in ``build`` Algorithm step 10).
    """
    return resolve_runtime_dir("builds")


def clean_build_runtime_dir(host_dir: Path) -> None:
    """Recursively wipe the ralphex runtime directory and recreate it empty; idempotent.

    Args:
        host_dir: Host path computed by :func:`resolve_build_runtime_dir`.

    Raises:
        OSError: Propagated by ``rmtree`` on any failure other than the
            directory vanishing between the existence check and ``rmtree``
            (e.g. a concurrent ``goga build --clean`` on the same
            project/branch). The wipe must be total, so a partial removal
            surfaces as an error rather than silently leaving stale state
            mounted into the next run.
    """
    if host_dir.exists():
        # Tolerate a directory that vanishes between the check and rmtree (a
        # concurrent --clean); any other failure propagates — the wipe is total.
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(host_dir)
    host_dir.mkdir(parents=True, exist_ok=True)


def _cleanup_ralphex_in_project(project_dir: Path) -> None:
    """Remove the Docker-created ``.ralphex/`` mount point from the project dir; no-op when absent.

    Args:
        project_dir: Host project directory (the ``/workspace`` bind-mount
            source) potentially containing a Docker-created ``.ralphex/``.
    """
    # The directory may vanish between the check and rmtree (concurrent process
    # or a crash cleanup race); tolerate that. Any other failure propagates so
    # an unexpected filesystem state surfaces rather than silently leaving
    # ``.ralphex/`` behind and violating the contract.
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(project_dir / ".ralphex")


@click.command()
@click.argument("plan")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
@click.option("--skip-manifest-check", is_flag=True, help="Skip CODEMANIFEST uncommitted check")
@click.option("--session-timeout", type=str, default=None, help="Session timeout")
@click.option("--idle-timeout", type=str, default=None, help="Idle timeout")
@click.option("--wait", type=str, default=None, help="Wait time")
@click.option("--max-iterations", type=int, default=None, help="Max iterations")
@click.option(
    "--review-patience",
    type=int,
    default=None,
    help="External review patience (consecutive unchanged rounds); addresses build.review.additional.patience",
)
@click.option(
    "--base-ref",
    type=str,
    default=None,
    help="Review diff base (branch name or commit hash); addresses build.review.base_ref",
)
@click.option(
    "-w",
    "--workflow",
    "workflow",
    type=str,
    default=None,
    help="Workflow that drives the build; validated against .goga/workflows/, forwarded in-container",
)
@click.option(
    "-p",
    "--profile",
    "profile",
    type=str,
    default=None,
    help="Contributor-profile activation channel; overrides GOGA_PROFILE, forwarded in-container",
)
@click.option("-e", "--env", "extra_env", multiple=True, help="Pass env var to container (KEY=VALUE)")
@click.option("--proxy", type=str, default=None, help="HTTP/HTTPS proxy URL; overrides config.build.proxy")
@click.option(
    "--add-host",
    "add_host",
    multiple=True,
    help="Add a docker run --add-host HOST:IP entry; merges on top of config.build.hosts",
)
@click.option(
    "-c",
    "--clean",
    "clean",
    is_flag=True,
    default=False,
    help="Wipe the persistent ralph-loop runtime host directory before launch",
)
@click.option(
    "--update",
    "-u",
    "update",
    is_flag=True,
    default=False,
    help="Refresh the image before launch (build if a project Dockerfile is declared, else pull)",
)
@click.option(
    "--skip-review/--no-skip-review",
    "skip_review",
    default=None,
    help="Skip the review phase (--skip-review) or force the full cycle (--no-skip-review); "
    "overrides build.review.skip in .goga/config.yml",
)
@click.pass_context
def build(  # noqa: PLR0913, C901, PLR0915, PLR0912, PLR0917
    ctx: click.Context,
    plan: str,
    dry_run: bool,
    skip_manifest_check: bool,
    session_timeout: str | None,
    idle_timeout: str | None,
    wait: str | None,
    max_iterations: int | None,
    review_patience: int | None,
    base_ref: str | None,
    workflow: str | None,
    profile: str | None,
    extra_env: tuple[str, ...],
    proxy: str | None,
    add_host: tuple[str, ...],
    update: bool,
    clean: bool,
    skip_review: bool | None,
) -> None:
    """Build code via a ralph-loop by launching goga.build inside a Docker container.

    Inside the goga container itself (the GOGA_DOCKER=1 marker) the command
    instead executes the SAME composed in-container command directly as a
    child process; the host-only options (-e/--env, --add-host, --proxy,
    -u/--update) are rejected there with an error naming the option before
    any other work — they configure the docker launch, which does not exist
    in-container.
    \f
    Home (machine-wide) config from ``~/.goga/config.yml`` is applied up front:
    ``home.env`` is the lowest-priority container environment layer (git identity
    and CLI ``-e`` win on conflict), ``home.docker.run`` is forwarded to every
    ``docker run``, and ``home.docker.build`` is forwarded to image builds. An
    absent home file is ignored. The task env (``build.env``) is NOT part of the
    container env-file — it reaches the container through the mounted
    ``.goga/config.yml`` and is applied in-container as the tasks-pass layer.
    """
    # Step 1a — resolve the execution substrate once; on the direct path
    # (inside the goga image, the GOGA_DOCKER marker) reject every host-only
    # option BEFORE any other work — the docker-CLI check, the config load,
    # no env assembly, no launch. Each option configures the docker launch,
    # which does not exist inside the container; nothing is silently ignored.
    # The host path (marker absent) skips this step entirely.
    direct = is_in_docker()

    if direct:
        host_only = [
            ("--env/-e", bool(extra_env)),
            ("--add-host", bool(add_host)),
            ("--proxy", proxy is not None),
            ("--update/-u", update),
        ]

        for flag, passed in host_only:
            if passed:
                raise click.ClickException(
                    f"{flag} is host-only: it configures the docker launch, "
                    f"which does not exist inside the goga container"
                )

    # Step 1 — docker-CLI gate (host substrate only): inside the goga image
    # there is no docker launch to check or acquire.
    if not direct and not _check_docker():
        raise click.ClickException("docker not found in PATH")

    # Home (machine-wide) config preamble — an empty HomeConfig when the file is
    # absent (no-op). home.env is the lowest-priority env layer (step 7);
    # home.docker.run reaches every docker run and home.docker.build every image
    # build as a separate extra_args keyword. A malformed home file surfaces as a
    # clean ClickException per the click-wrapping convention (absence is normal).
    try:
        home: HomeConfig = load_home_config()
    except (ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        authored = load_project_config()
        # The config-amendment checkpoint joins the load inside the try: a
        # hard checkpoint failure is the same clean error as a failed load.
        # The home configuration load above stays authored-only (closed
        # surface) — only the project configuration carries a checkpoint.
        overlay = ConfigHooks().amend_config(config=authored)
    except (FileNotFoundError, KeyError, ValueError, ImportError, yaml.YAMLError) as exc:
        # ImportError — a broken tool package facade during the registry
        # build — is the same clean error, never a raw traceback.
        raise click.ClickException(str(exc)) from exc

    for line in overlay.summary_lines:
        click.echo(line, err=True)

    # Every downstream field access — the guards, the image, the launch —
    # is unchanged code reading the effective object.
    config = overlay.config

    # Step 2.1 — host-side structural None-guard: the build section is optional
    # at the loader level (load_project_config returns config.build=None when
    # absent), but `goga build` cannot run without it. Raise a clean
    # ClickException BEFORE any config.build.* access and BEFORE the secret
    # env-file write (step 9), so a build-less config surfaces as a clean
    # message + exit 1 rather than an AttributeError, and the in-container
    # goga.build never starts (no docker run, no secret env-file leak on disk).
    # The agent VALUE guard stays in-container (goga/build): the effective agent
    # may arrive as a container-side amendment, so a host check would reject a
    # run an amendment could have satisfied.
    if config.build is None:
        raise click.ClickException("build section is required in .goga/config.yml to run 'goga build'")

    # Step 3.1 — argv parsability of the two new channels. Click consumes any
    # next token as an option value, so `-w "-x"` parses on the host with the
    # dash-leading token swallowed as the name — but the in-container argparse
    # surface classifies it as an option and dies only AFTER the whole launch
    # ceremony. Reject both forms here, before any docker activity (mirroring
    # the pipeline command's workflow name rule).
    if workflow is not None and workflow.startswith("-"):
        raise click.ClickException(f"invalid workflow name {workflow!r}")

    if profile is not None and profile.startswith("-"):
        raise click.ClickException(f"invalid profile name {profile!r}")

    # Step 3.2 — light host-side diagnostic for an explicit -w: path
    # containment + file existence under <cwd>/.goga/workflows/ (the same
    # resolution root the in-container build composes). The file itself is
    # NEVER read here — a typo surfaces as a clean message + exit 1 before
    # any docker activity, and an escaping name (``..`` segment, absolute
    # prefix) is never resolved into the wider filesystem.
    if workflow is not None:
        workflows_root = (Path.cwd() / ".goga" / "workflows").resolve()
        workflow_path = workflows_root / f"{workflow}.yml"

        try:
            workflow_path.resolve().relative_to(workflows_root)
        except ValueError:
            raise click.ClickException(f"invalid workflow name {workflow!r}") from None

        if not workflow_path.exists():
            raise click.ClickException(f"workflow '{workflow}' not found at {workflow_path}")

    cli_flags = {
        "skip_manifest_check": skip_manifest_check,
        "skip_review": skip_review,
        "session_timeout": session_timeout,
        "idle_timeout": idle_timeout,
        "wait": wait,
        "max_iterations": max_iterations,
        "review_patience": review_patience,
        "base_ref": base_ref,
        "workflow": workflow,
        "profile": profile,
        "dry_run": dry_run,
    }

    # Resolve the proxy: the --proxy CLI value wins over config.build.proxy.
    resolved_proxy = proxy if proxy is not None else config.build.proxy

    # Resolve hosts: merge config.build.hosts with parsed --add-host entries.
    # Each "HOST:IP" string is split on the first colon; CLI entries override
    # config entries on host-key conflict. Format is not validated beyond the
    # split — Docker reports malformed entries itself.
    merged_hosts: dict[str, str] = {**config.build.hosts}

    for entry in add_host:
        host, _, ip = entry.partition(":")
        merged_hosts[host] = ip

    # Step 6 — read the git identity (tolerated absent, no error).
    git_env = _read_git_config()

    # Step 7 — the home bundle loads ONCE here, before any docker activity: a
    # malformed home profile is one clean error (no image refresh, no launch),
    # and the payload value itself never appears in any message.
    try:
        home_profiles = load_home_profiles(Path.home() / ".goga" / "profiles")
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    # The env ladder — one composition, two sinks (per direct-runner): the
    # host substrate writes these lines into the private env-file (step 9);
    # the direct substrate parses them into the child env layer (step 14a).
    # The raw CLI lines and the payload compose from the SAME parsed values
    # (one source, two carriers per the extra-env-carriage practice — never
    # parsed or filtered independently). The task env (config.build.env) is
    # NOT part of the lines — it reaches the container only through the
    # mounted .goga/config.yml and is applied in-container at the pass
    # launches.
    lines = _compose_env_lines(home.env, git_env, extra_env, resolved_proxy, home_profiles)

    # Step 14a — the direct substrate: execute the SAME composed command line
    # and env contract as a child of the current environment. Substrate-scoped
    # skips: the image guard below, the host ralphex runtime-dir machinery,
    # the env-file write, the docker-run assembly, docker_build_if_not_exist,
    # docker_update, DockerRunner, and the caller-side D7 handler — run_direct
    # owns the signals (SIGTERM/SIGINT forwarded to the child, exit 128 +
    # signum). Ralphex state does not persist across direct runs (no host
    # runtime mount exists on this path) — an accepted, documented property.
    if direct:
        # --clean wipes the directory ralphex actually uses without the nested
        # bind-mount — the cwd-relative .ralphex of the project — BEFORE the
        # run, never after.
        if clean:
            with contextlib.suppress(FileNotFoundError):
                shutil.rmtree(Path.cwd() / ".ralphex")

        args = ["-m", "goga.build", plan, *_cli_flags_to_args(cli_flags)]

        try:
            if dry_run:
                # The direct command line — the same argv the spawn below
                # would execute — printed, never executed (the ralphex
                # launcher's dry-run pattern: command lines only).
                print(shlex.join(["python3", *args]), file=sys.stderr)
                ctx.exit(0)

            # The spawn failure channel (D5): run_direct propagates a raw
            # OSError from Popen (the executor never wraps); the caller owns
            # the wrapping, so a missing/unusable program token is the same
            # clean message + exit 1 as every other failure of the command.
            try:
                exit_code = run_direct(["python3", *args], env=_env_overlay(lines))
            except OSError as exc:
                raise click.ClickException(str(exc)) from exc

            ctx.exit(exit_code)
        finally:
            # The no-.ralphex-in-project invariant holds under every exit
            # path on BOTH substrates.
            _cleanup_ralphex_in_project(Path.cwd())

    # Step 8 — reject the missing-image case before creating any temp files: the
    # env file (written below) carries git identity and CLI -e secrets and is
    # only unlinked by the finally of the try block below, so creating it here
    # and then raising would leak it on disk.
    if config.image is None:
        raise click.ClickException("image in .goga/config.yml is not set")

    # Resolve and prepare the host ralphex runtime directory BEFORE writing the
    # secret-bearing env file: mkdir/clean can raise (read-only home, permission
    # denied), and the env file is only unlinked by the finally below — so
    # writing it first would leak git identity and CLI -e secrets on disk
    # if the runtime-dir setup raised. Docker may also refuse to bind-mount a
    # non-existent host path, so the directory must exist before docker run.
    # When --clean is set, wipe and recreate it so ralphex starts from a fresh
    # state; the default preserves progress files across runs of the same
    # project+branch.
    runtime_dir = resolve_build_runtime_dir()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    if clean:
        clean_build_runtime_dir(runtime_dir)

    container_name = f"goga-build-{os.getpid()}"

    def _on_signal(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    # D7 leak-prevention invariant: install BOTH the SIGTERM and SIGINT handlers
    # BEFORE writing the secret-bearing env file, and write that file inside the
    # try below — so a signal (or any exception) raised in the window that spans
    # the env-file write, the docker_update build, and the DockerRunner launch
    # propagates through the finally, which unlinks the env file. Writing the env
    # file before the handlers are installed would leak git identity and CLI -e
    # secrets on disk if a signal arrived in that window. The
    # runner later installs its own handler that NESTS under these (saving and
    # restoring them), so the restores below return to the originals.
    _prev_term = signal.signal(signal.SIGTERM, _on_signal)
    _prev_int = signal.signal(signal.SIGINT, _on_signal)

    env_file: Path | None = None
    try:
        env_file = _write_env_file(lines)

        project_dir = Path.cwd().resolve()
        # Nested bind-mount: ralphex writes state to its cwd-relative .ralphex/
        # which this mount resolves into the host runtime directory — so ralphex
        # bytes never land in the user's project directory. Read-write (ralphex
        # writes).
        mounts = [f"{project_dir}:/workspace", f"{runtime_dir}:/workspace/.ralphex"]

        # args = the post-image command (the in-container goga.build invocation +
        # its flags); params = the docker-run options the runner translates to
        # flags via the shared param→flag rule.
        args = ["-m", "goga.build", plan, *_cli_flags_to_args(cli_flags)]
        params = {
            "name": container_name,
            "rm": True,
            "entrypoint": "python3",
            "workdir": "/workspace",
            "v": mounts,
            "add_host": [f"{host}:{ip}" for host, ip in merged_hosts.items()],
            "env_file": str(env_file),
        }

        if dry_run:
            # The assembled launch line — the same param→flag translation and
            # argv order DockerRunner would launch — printed, never executed
            # (the ralphex launcher's dry-run pattern: command lines only).
            print(
                shlex.join(["docker", "run", *translate_params(params), config.image, *args]),
                file=sys.stderr,
            )
            ctx.exit(0)

        # First-run safety net: build the local image if it is absent and a
        # project Dockerfile is declared. No-op when the image already exists
        # or when no Dockerfile is set. Fatal build propagates as ClickException
        # (D5 — clean message + exit 1, no traceback). Runs inside the try so
        # the D7 leak-prevention invariant covers this window too: the secret
        # env-file is already written above, and a fatal build unwinds to the
        # finally below which unlinks it.
        try:
            docker_build_if_not_exist(config.image, config.dockerfile, extra_args=home.docker.build)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

        if update:
            # docker_update owns the build-vs-pull branch (build when a project
            # Dockerfile is declared — fatal; else pull — WARNING, non-fatal).
            # D5: a fatal build surfaces as a clean message + exit 1 rather than
            # a traceback; pull-branch failures stay a WARNING inside docker_pull.
            try:
                docker_update(config.image, config.dockerfile, extra_args=home.docker.build)
            except Exception as exc:
                raise click.ClickException(str(exc)) from exc

        exit_code = DockerRunner(config.image).run(args, extra_args=home.docker.run, **params)
        ctx.exit(exit_code)
    finally:
        # Unlink the env file only if it was created: a pre-write failure or a
        # dry_run ctx.exit before the write leaves env_file None. The env file
        # carries git identity and CLI -e secrets.
        if env_file is not None:
            env_file.unlink(missing_ok=True)
        # Remove the Docker-created empty ``.ralphex/`` mount point from the
        # project directory: applying the nested bind-mount
        # ``runtime_dir:/workspace/.ralphex`` on top of the ``/workspace``
        # project mount makes Docker Engine create ``/workspace/.ralphex``
        # inside the bind-mount source — i.e. physically in the user's project
        # directory. The directory is empty (in-container writes land in the
        # nested mount = host runtime dir) but survives container exit because
        # bind-mount mutations are persistent. The CODEMANIFEST contract
        # forbids ``.ralphex/`` in the project directory under any exit path,
        # so it is removed unconditionally here. No-op on dry_run (docker never
        # runs, no mount point is created) and on any path where the directory
        # does not exist. The runner's own ``docker kill`` + handler restore
        # already ran in its inner finally (before this one).
        _cleanup_ralphex_in_project(Path.cwd())
        signal.signal(signal.SIGTERM, _prev_term)
        signal.signal(signal.SIGINT, _prev_int)
