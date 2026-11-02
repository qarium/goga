"""Host-side docker launcher for ``goga pipeline``."""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import signal
import socket
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import click
import yaml

from ...config import HomeConfig, ProjectConfig, load_home_config
from ...docker import (
    DockerRunner,
    docker_build_if_not_exist,
    docker_update,
    encode_extra_env,
    is_in_docker,
    profile_carriage_lines,
    run_direct,
)
from ...runtime import resolve_runtime_dir
from .file_roots import collect_file_roots, encode_file_roots

logger = logging.getLogger(__name__)

# The in-container path afm state is mounted on and ``AFM_DIR`` points at. The
# value travels through the env-file engine line (skipped when the CLI
# explicitly supplied the key); the afm configuration file at the fixed
# in-container home path is authored in-container by the run coordination, so
# no host-side derivation of it exists anymore.
_IN_CONTAINER_AFM_DIR = "/home/goga/pipeline"


def _check_docker() -> bool:
    """Check whether the docker CLI is available on PATH.

    Returns:
        True if ``docker --version`` exits successfully, False otherwise.
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
    """Write environment lines to a private temporary env file (mode 0600).

    Args:
        lines: The fully assembled KEY=VALUE lines of the container env-file,
            in ladder order (the ``GOGA_EXTRA_ENV`` payload line last).

    Returns:
        Path to the written temporary file.
    """
    fd, path = tempfile.mkstemp(prefix="goga-pipeline-env-")

    with os.fdopen(fd, "w") as f:
        Path(path).chmod(stat.S_IRUSR | stat.S_IWUSR)

        for line in lines:
            f.write(f"{line}\n")

    return Path(path)


def _allocate_port() -> int:
    """Allocate a free localhost TCP port by binding to an ephemeral port.

    Returns:
        The allocated port number — a socket bound to ``("", 0)`` is read and
        closed; a small race window is accepted (the port may be reused
        before the container binds it).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.bind(("", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def resolve_pipeline_runtime_dir(pipeline_name: str) -> Path:
    """Compute the persistent afm state host directory for a pipeline.

    Args:
        pipeline_name: Pipeline name without extension (the run-mode name
            arg); every ``:`` is replaced with ``-`` before path
            composition — an unsanitized ``:`` would be parsed by docker as
            the ``source:target[:mode]`` separator of the runtime-dir
            bind-mount. The ORIGINAL name still feeds the in-container run
            argv and the workflow auto-match basename.

    Returns:
        Absolute host path
        ``~/.goga/runtime/pipelines/<normalized>/<branch>/<sanitized_name>``
        where ``<sanitized_name>`` is ``pipeline_name`` with ``:`` → ``-``.
        Pure with respect to the filesystem — the directory is NOT created
        here (creation is the caller's responsibility).
    """
    return resolve_runtime_dir("pipelines", pipeline_name.replace(":", "-"))


def clean_pipeline_runtime_dir(pipeline_runtime_dir: Path) -> None:
    """Recursively wipe and recreate the persistent afm state directory; idempotent.

    Args:
        pipeline_runtime_dir: Host path computed by
            :func:`resolve_pipeline_runtime_dir`.

    Raises:
        OSError: Propagated by ``rmtree`` on any failure other than the
            directory vanishing between the existence check and ``rmtree``
            (e.g. a concurrent ``goga pipeline --clean`` on the same
            project/branch/name). The wipe must be total, so a partial
            removal surfaces as an error rather than silently leaving stale
            state mounted into the next run.
    """
    if pipeline_runtime_dir.exists():
        # Tolerate a directory that vanishes between the check and rmtree (a
        # concurrent --clean); any other failure propagates — the wipe is total.
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(pipeline_runtime_dir)

    pipeline_runtime_dir.mkdir(parents=True, exist_ok=True)


def _resolve_workflow_env_name(
    workflow: str | None,
    no_workflow: bool,
    name: str,
) -> str | None:
    """Compute the effective workflow name of the run decision (env-line role).

    Args:
        workflow: optional workflow name from the ``--workflow`` CLI flag.
        no_workflow: flag from the ``--no-workflow`` CLI flag.
        name: pipeline name without extension (the auto-match basename).

    Returns:
        The name the ``GOGA_WORKFLOW`` engine line carries, or ``None`` when
        no workflow will be applied and no line is written —
        ``no_workflow is True`` → ``None`` (workflow application is
        disabled); ``workflow is not None`` (explicit ``--workflow``, file
        already validated by the caller) → ``workflow``; else the
        auto-match fallback ``<cwd>/.goga/workflows/<name>.yml`` — ``name``
        when it exists (the in-container routine resolves the basename
        fallback itself, so the argv carries neither workflow flag), or
        ``None`` when absent (in-container silent-miss, no line).

    Note:
        Workflow paths are project-only — resolved from ``Path.cwd()``
        (which is ``/workspace`` in-container), mirroring the in-container
        resolution. The name travels to the container ONLY through the
        env-file engine line; the workflow flags travel as argv, and the
        launch feedback line prints in-container (the host prints no
        workflow line).
    """
    if no_workflow:
        return None
    if workflow is not None:
        return workflow

    # Auto-match fallback: the basename workflow-file is resolved in-container,
    # so the argv carries neither workflow flag. The host only checks existence
    # to decide whether the engine line is accurate (the file will actually
    # apply). Workflow paths are project-only — mirroring the
    # explicit-``--workflow`` and in-container containment guards, a ``name``
    # carrying a ``..`` segment or an absolute prefix that escapes the
    # workflows dir is a silent miss (``None``, no line), never a path
    # resolved into the wider filesystem. The in-container resolver re-applies
    # the same containment before parsing, so this only keeps the engine line
    # honest.
    workflows_root = (Path.cwd() / ".goga" / "workflows").resolve()
    auto_match_path = workflows_root / f"{name}.yml"

    try:
        auto_match_path.resolve().relative_to(workflows_root)
    except ValueError:
        return None

    if auto_match_path.exists():
        return name

    return None


def _compose_env_lines(  # noqa: PLR0913, PLR0917
    home_env: dict[str, str],
    docker_run_tokens: list[str],
    extra_env: tuple[str, ...],
    proxy: str | None,
    ambient_profile: str = "",
    home_profiles: dict[str, dict[str, Any]] | None = None,
    workflow_name: str | None = None,
) -> list[str]:
    """Compose the run-mode env lines (Algorithm step 8) — environment layers only.

    The single composition shared by both execution substrates (one
    composition, two sinks — per ``direct-runner``): the host path writes the
    lines into the private env-file consumed by ``docker run --env-file``; the
    direct path parses them into the child env layer of ``run_direct``.

    Args:
        home_env: ``home.env`` from the machine-wide home config — the
            lowest-priority env layer (git identity and CLI win on key
            conflict). Survives where unconflicted.
        docker_run_tokens: ``home.docker.run`` tokens (already shell-tokenized,
            consumed verbatim per the ``home-configuration`` contract) from
            which the ``AFM_DOCKER_FILE_ROOTS`` file-manager roots are
            composed — the project root plus one extra root per directory
            mount. Written on EVERY run launch unless the CLI explicitly
            supplied the key (the escape hatch).
        extra_env: Additional raw KEY=VALUE strings written verbatim (a
            SEPARATE channel above the dict layers, winning on key conflict)
            and encoded into the payload line from the same values.
        proxy: Resolved HTTP/HTTPS proxy URL; populates the proxy env vars when
            non-None.
        ambient_profile: The ambient host ``GOGA_PROFILE`` value — written as
            the ``GOGA_PROFILE`` engine line only when non-empty (the CLI
            activation channel travels as argv instead).
        home_profiles: The loaded home bundle (the ``load_home_profiles``
            result of the caller, None when empty) — encoded into the
            ``GOGA_HOME_PROFILES`` engine line only when non-empty (per
            ``home-profiles-carriage``); the payload never appears in any
            message.
        workflow_name: The effective workflow name of the run decision (the
            ``_resolve_workflow_env_name`` result) — written as the
            ``GOGA_WORKFLOW`` engine line only when a workflow will be
            applied; None writes no line.

    Returns:
        The fully assembled KEY=VALUE lines in ladder order (the
        ``GOGA_EXTRA_ENV`` payload line last).

    Note:
        Ladder order (lowest to highest): ``home_env`` as the BASE layer
        under git identity, the raw ``extra_env`` lines, the engine
        variables (``AFM_DIR``, ``AFM_DOCKER_FILE_ROOTS``, and the proxy
        triple when ``proxy`` is set), the ``GOGA_EXTRA_ENV`` payload line,
        then the three profile-carriage engine lines (``GOGA_PROFILE``,
        ``GOGA_HOME_PROFILES``, ``GOGA_WORKFLOW`` — each written only when
        it carries cargo). The engine lines follow the CLI lines and SKIP a
        key the CLI explicitly supplied — the raw CLI line keeps winning
        without a duplicate launcher line (the documented
        ``-e AFM_DOCKER_FILE_ROOTS=...`` escape hatch); the payload line is
        always written (last-write-wins keeps it ahead of any CLI line of
        the same key). The task env layer (``config.pipeline.env``) and the
        skip names NEVER enter the lines — they apply in-container /
        travel as argv.
    """
    # home.env is the BASE layer — lowest priority; git identity overrides it.
    # The CLI raw channel and the engine lines are appended after the base
    # lines, so they still win on key conflict.
    base = {**home_env, **_read_git_config()}

    # Engine variables — launch mechanics nothing overrides. AFM_DIR redirects
    # afm state (flows, run-state) to the rw-mounted persistent directory at
    # /home/goga/pipeline; ~/.afm/config.yaml stays the config source
    # regardless (see the `afm` practice — the file is authored in-container).
    # The afm file-manager roots layer (the `afm` practice): the ordered roots
    # of this launch — the project root first, then one extra root per
    # home.docker.run directory mount — canonically encoded as base64 compact
    # JSON. goga is only the PRODUCER of the payload; afm (in-container)
    # decodes it. Written on EVERY run launch; repeated launches with
    # unchanged mounts produce the identical value.
    engine: dict[str, str] = {
        "AFM_DIR": _IN_CONTAINER_AFM_DIR,
        "AFM_DOCKER_FILE_ROOTS": encode_file_roots(collect_file_roots(docker_run_tokens)),
    }

    if proxy is not None:
        engine["HTTP_PROXY"] = proxy
        engine["HTTPS_PROXY"] = proxy
        engine["NO_PROXY"] = "localhost,127.0.0.1"

    # The engine-line skip rule: a key the CLI explicitly supplied is not
    # written by the launcher — the user's own line keeps winning under docker
    # --env-file last-write-wins without a duplicate launcher line.
    cli_keys = {pair.partition("=")[0] for pair in extra_env if "=" in pair}
    engine = {key: value for key, value in engine.items() if key not in cli_keys}

    lines = [f"{key}={value}" for key, value in base.items()]
    lines += list(extra_env)
    lines += [f"{key}={value}" for key, value in engine.items()]

    # The payload line — the second carrier composed from the SAME parsed CLI
    # values as the raw lines above (one source, two carriers), written on
    # every launch. Last-write-wins gives it precedence over any CLI line of
    # the same key.
    lines.append(f"GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}")

    # The contributor-profile carriage — three engine lines after the payload
    # line, composed by the shared `profile_carriage_lines` helper (same
    # engine-skip rule: an explicit -e key keeps winning; each line written
    # only when it carries cargo): the ambient profile name, the whole
    # encoded home bundle (the effective profile may only become known
    # in-container — the workflow ``profile:`` default), and the effective
    # workflow name of the run decision. The payload values never appear in
    # any message.
    lines += profile_carriage_lines(ambient_profile, home_profiles, workflow_name, cli_keys)

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


def _build_env_file(  # noqa: PLR0913, PLR0917
    home_env: dict[str, str],
    docker_run_tokens: list[str],
    extra_env: tuple[str, ...],
    proxy: str | None,
    ambient_profile: str = "",
    home_profiles: dict[str, dict[str, Any]] | None = None,
    workflow_name: str | None = None,
) -> Path:
    """Build the run-mode env-file (Algorithm step 8) — the host sink of the shared lines.

    A thin wrapper over ``_compose_env_lines`` (the one composition both
    substrates share): composes the ladder lines and writes them into the
    private temporary env-file consumed by ``docker run --env-file``.

    Args:
        home_env: ``home.env`` from the machine-wide home config — the
            lowest-priority env layer (git identity and CLI win on key
            conflict). Survives where unconflicted.
        docker_run_tokens: ``home.docker.run`` tokens (already shell-tokenized,
            consumed verbatim per the ``home-configuration`` contract) from
            which the ``AFM_DOCKER_FILE_ROOTS`` file-manager roots are
            composed — the project root plus one extra root per directory
            mount. Written on EVERY run launch unless the CLI explicitly
            supplied the key (the escape hatch).
        extra_env: Additional raw KEY=VALUE strings written verbatim (a
            SEPARATE channel above the dict layers, winning on key conflict)
            and encoded into the payload line from the same values.
        proxy: Resolved HTTP/HTTPS proxy URL; populates the proxy env vars when
            non-None.
        ambient_profile: The ambient host ``GOGA_PROFILE`` value — written as
            the ``GOGA_PROFILE`` engine line only when non-empty (the CLI
            activation channel travels as argv instead).
        home_profiles: The loaded home bundle (the ``load_home_profiles``
            result of the caller, None when empty) — encoded into the
            ``GOGA_HOME_PROFILES`` engine line only when non-empty (per
            ``home-profiles-carriage``); the payload never appears in any
            message.
        workflow_name: The effective workflow name of the run decision (the
            ``_resolve_workflow_env_name`` result) — written as the
            ``GOGA_WORKFLOW`` engine line only when a workflow will be
            applied; None writes no line.

    Returns:
        Path to the written private env-file.
    """
    return _write_env_file(
        _compose_env_lines(
            home_env=home_env,
            docker_run_tokens=docker_run_tokens,
            extra_env=extra_env,
            proxy=proxy,
            ambient_profile=ambient_profile,
            home_profiles=home_profiles,
            workflow_name=workflow_name,
        )
    )


def _compose_run_args(  # noqa: PLR0913, PLR0917
    name: str,
    port: int,
    workflow: str | None,
    no_workflow: bool,
    profile: str | None,
    skip: tuple[str, ...],
    parallel: int | None,
    fail_on_error: bool = False,
) -> list[str]:
    """Compose the in-container run argv (Algorithm step 9 — the argv channel).

    Args:
        name: Pipeline name without extension.
        port: The allocated localhost port (mirrors the docker ``-p`` publish).
        workflow: optional workflow name from the ``--workflow`` CLI flag.
        no_workflow: flag from the ``--no-workflow`` CLI flag.
        profile: optional profile name from the ``-p/--profile`` CLI flag —
            the CLI activation channel, appended as ``--profile <profile>``
            only when set.
        skip: raw stage names from the repeatable ``-s/--skip`` CLI option.
        parallel: optional int capping concurrently executing stages.
        fail_on_error: the run-form fail-fast decision from the
            ``--fail-on-error`` CLI flag — appended as ``--fail-on-error``
            only when True (the in-container ``pipeline_cli`` threads it onto
            the engine's ``--exit-on-fail``); False (default) omits the flag.

    Returns:
        The post-image command handed to ``DockerRunner.run`` (or, prefixed
        with the ``python3`` program token, to ``run_direct`` on the direct
        substrate):
        ``["-m","goga.pipeline","run",<name>,"--port",<port>]`` followed,
        in order, by the workflow decision (``-w <workflow>`` when
        explicit, else ``--no-workflow`` when set, else neither flag — the
        in-container run coordination attempts the basename auto-match
        fallback itself), then ``--profile <profile>`` only when set, then
        one ``-s <name>`` per skip entry (forwarded as parsed — no
        validation, no dedup; unknown names are the in-container compiler's
        structural error), then ``--parallel <parallel>`` only when not
        None, then ``--fail-on-error`` only when True.
    """
    args = ["-m", "goga.pipeline", "run", name, "--port", str(port)]

    # The workflow decision travels as argv, exactly as given: -w <workflow>
    # when explicit, else --no-workflow when set, else neither flag. The elif
    # keeps the assembly total even though the caller rejects the combination.
    if workflow is not None:
        args += ["-w", workflow]
    elif no_workflow:
        args += ["--no-workflow"]

    # The CLI activation channel — --profile <profile> only when set (the env
    # channel and the workflow default resolve in-container; the ambient value
    # travels separately through the env-file engine line).
    if profile is not None:
        args += ["--profile", profile]

    # One -s <name> per skip entry — forwarded as parsed, no validation, no
    # dedup (unknown names are the in-container compiler's structural error).
    for skip_name in skip:
        args += ["-s", skip_name]

    # --parallel is appended ONLY when not None (absent ⇒ no flag ⇒ afm
    # unbounded). The in-container pipeline_cli forwards it to afm's
    # --max-parallel. Distinct from the Docker -p <port>:<port> port-publish
    # token.
    if parallel is not None:
        args += ["--parallel", str(parallel)]

    # --fail-on-error is appended ONLY when True (absent ⇒ no flag ⇒ the run
    # launches with no fail-fast flag). The in-container pipeline_cli forwards
    # it to the engine's --exit-on-fail.
    if fail_on_error:
        args += ["--fail-on-error"]

    return args


def _run_named(  # noqa: PLR0913, PLR0917
    name: str,
    config: ProjectConfig,
    home: HomeConfig,
    container_name: str,
    extra_env: tuple[str, ...],
    proxy: str | None,
    hosts: dict[str, str] | None,
    clean: bool,
    update: bool,
    workflow: str | None,
    no_workflow: bool,
    profile: str | None = None,
    skip: tuple[str, ...] = (),
    parallel: int | None = None,
    home_profiles: dict[str, dict[str, Any]] | None = None,
    fail_on_error: bool = False,
) -> int:
    """Launch the container in run mode (``-m goga.pipeline run <name> --port``).

    Args:
        name: Pipeline name without extension.
        config: Loaded project configuration, consumed for the host-owned
            launch fields only (``image``/``dockerfile``); the run-parameter
            fields (``pipeline.agent``/``pipeline.env``) are read nowhere here.
        home: Loaded machine-wide home config. ``home.env`` is layered as the
            BASE (lowest-priority) env layer in the env-file; ``home.docker.run``
            is forwarded to ``DockerRunner.run`` as ``extra_args``;
            ``home.docker.build`` is forwarded to ``docker_build_if_not_exist``
            and ``docker_update`` (build branch only).
        container_name: Name assigned to the container.
        extra_env: Additional raw KEY=VALUE strings forwarded into the container
            env-file (e.g. agent authorization tokens).
        proxy: Resolved HTTP/HTTPS proxy URL. When non-None, populates
            ``HTTP_PROXY``/``HTTPS_PROXY``/``NO_PROXY`` in the env-file.
        hosts: Resolved host→IP mapping forwarded as ``--add-host`` flags.
        clean: When True, wipe the persistent afm state directory before launch.
        update: When True, refresh the image before launch via ``docker_update``
            (build when a Dockerfile is declared, else pull).
        workflow: optional workflow name from ``--workflow``. Appended to the
            in-container argv as ``-w <workflow>`` and carried by the
            ``GOGA_WORKFLOW`` engine line. The file existence was already
            validated by the caller.
        no_workflow: flag from ``--no-workflow``. When True, ``--no-workflow``
            joins the in-container argv and no ``GOGA_WORKFLOW`` line is
            written (mutually exclusive with ``workflow``, enforced by
            caller).
        profile: optional profile name from ``--profile`` — the CLI activation
            channel, appended to the in-container argv as
            ``--profile <profile>`` only when set.
        skip: raw stage names from the repeatable ``-s/--skip`` CLI option. Each
            name appends one ``-s <name>`` to the in-container argv — forwarded
            as parsed (no validation, no dedup); the in-container
            ``run_pipeline`` routine applies ``apply_skip_stages`` over the
            resolved workflow.
        parallel: optional int capping concurrently executing stages. When not
            None, appended to the in-container run argv as
            ``--parallel <parallel>`` (after ``--port`` and the workflow/skip
            flags, before the container launch) so the in-container
            ``pipeline_cli`` forwards it to afm's ``--max-parallel``. When None
            (default), the flag is omitted — afm runs unbounded (backward
            compatible). Distinct from the Docker ``-p <port>:<port>``
            port-publish token.
        home_profiles: the loaded home bundle (the ``load_home_profiles``
            result of the caller, None when empty) — encoded into the
            ``GOGA_HOME_PROFILES`` engine line of the env-file only when
            non-empty (per ``home-profiles-carriage``).
        fail_on_error: the run-form fail-fast decision from the
            ``--fail-on-error`` CLI flag — appended to the in-container run
            argv as ``--fail-on-error`` ONLY when True (after ``--parallel``,
            before the container launch) so the in-container ``pipeline_cli``
            threads it onto the engine's ``--exit-on-fail``. When False
            (default), the flag is omitted (backward compatible).

    Returns:
        The container's exit code.

    Raises:
        click.ClickException: when a fatal image build or ``docker_update``
            failure is surfaced (D5) — wrapped with a clean message, exit 1.
        SystemExit: ``128 + signum`` when SIGTERM/SIGINT is received during
            the run (the installed handler raises; the ``finally`` unlinks
            the env-file and restores the previous handlers first).

    Note:
        Orchestration order: allocate a port; resolve and ensure the
        persistent afm state directory (wiping it first when ``clean``),
        before any signal handler or secret file exists; install the
        SIGTERM/SIGINT handlers BEFORE writing the secret env-file (D7) — a
        signal during the setup window, including the ``docker_update``
        build, unwinds to the ``finally`` and unlinks the secret file (the
        runner's own handler later NESTS under this one, saving and
        restoring it); write the env-file (environment layers plus the
        profile carriage — the ambient ``GOGA_PROFILE``, the encoded home
        bundle, and the effective workflow name of the run decision); pass
        the workflow decision, the profile value, and the skip names to the
        in-container argv as flags; optionally refresh the image via
        ``docker_update`` (forwarding ``home.docker.build`` to image build
        in the build branch only); run the container via ``DockerRunner``
        (forwarding ``home.docker.run`` as the separate ``extra_args``
        keyword). The host prints NO workflow line — the launch feedback
        line prints in-container. The persistent directory is never deleted
        in ``finally`` — only the env-file is unlinked.
    """
    port = _allocate_port()

    # Steps 5-6 - resolve the persistent afm state host directory and ensure it
    # exists BEFORE installing signal handlers or creating temp files: it must
    # be on disk and survive every exit path (including the signal-exit path),
    # and the optional --clean wipe happens here — strictly before launch, never
    # after. No secret file exists yet at this point.
    runtime_dir = resolve_pipeline_runtime_dir(name)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    if clean:
        clean_pipeline_runtime_dir(runtime_dir)

    def _on_signal(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    # Step 7 — D7 leak-prevention invariant: install BOTH the SIGTERM and
    # SIGINT handlers BEFORE writing the secret-bearing env-file, and write the
    # file inside the try below — so a signal (or any exception) raised in the
    # window that spans the env-file write, the docker_update build, and the
    # DockerRunner launch propagates through the finally, which unlinks the
    # secret file. Writing it before the handlers are installed would leak git
    # identity and pipeline secrets on disk if a signal arrived in that window.
    # The runner later installs its own handler that NESTS under these (saving
    # and restoring them), so the restores below return to the originals.
    prev_term = signal.signal(signal.SIGTERM, _on_signal)
    prev_int = signal.signal(signal.SIGINT, _on_signal)
    env_file: Path | None = None

    try:
        # Step 8 — the env-file carries environment layers PLUS the
        # contributor-profile carriage: the ambient GOGA_PROFILE value, the
        # encoded home bundle, and the effective workflow name of the run
        # decision (computed with the same silent containment guard the
        # in-container resolver applies — never a path resolved into the
        # wider filesystem). The host prints NO workflow line; the launch
        # feedback line prints in-container.
        env_file = _build_env_file(
            home_env=home.env,
            docker_run_tokens=home.docker.run,
            extra_env=extra_env,
            proxy=proxy,
            ambient_profile=os.environ.get("GOGA_PROFILE", ""),
            home_profiles=home_profiles,
            workflow_name=_resolve_workflow_env_name(workflow, no_workflow, name),
        )

        project_dir = Path.cwd().resolve()
        # Step 9 — mounts: the project as /workspace (container working dir)
        # and the persistent afm state host dir read-write at
        # /home/goga/pipeline (survives across runs). Nothing else — the afm
        # configuration file is authored in-container, and credential
        # provisioning is user-owned via home.docker.run/-e.
        mounts = [
            f"{project_dir}:/workspace",
            f"{runtime_dir}:{_IN_CONTAINER_AFM_DIR}",
        ]

        # args = the post-image command (the in-container goga.pipeline run call +
        # its port + the run-coordination flags); params = the docker-run options
        # the runner translates to flags via the shared param→flag rule.
        args = _compose_run_args(name, port, workflow, no_workflow, profile, skip, parallel, fail_on_error)
        params = {
            "name": container_name,
            "rm": True,
            "entrypoint": "python3",
            "workdir": "/workspace",
            "p": f"{port}:{port}",
            "v": mounts,
            "add_host": [f"{host}:{ip}" for host, ip in (hosts or {}).items()],
            "env_file": str(env_file),
        }

        # Step 10 — first-run safety net: build the local image if it is absent
        # and a project Dockerfile is declared. No-op when the image exists or
        # no Dockerfile is set. Fatal build surfaces as ClickException (D5).
        # Runs inside the try so the D7 leak-prevention invariant covers this
        # window: the secret env-file is already written above, and a fatal
        # build unwinds to the finally below which unlinks it.
        # home.docker.build is forwarded to image build (build branch only).
        try:
            docker_build_if_not_exist(config.image, config.dockerfile, extra_args=home.docker.build)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

        # Step 11 — the --update refresh.
        if update:
            # docker_update owns the build-vs-pull branch (build when a project
            # Dockerfile is declared — fatal; else pull — WARNING, non-fatal).
            # D5: a fatal build surfaces as a clean message + exit 1 rather than
            # a traceback; pull-branch failures stay a WARNING inside docker_pull.
            # home.docker.build forwarded in the build branch only (ignored on pull).
            try:
                docker_update(config.image, config.dockerfile, extra_args=home.docker.build)
            except Exception as exc:
                raise click.ClickException(str(exc)) from exc

        # Step 12 — extra_args is a SEPARATE keyword to DockerRunner.run (NOT
        # part of params, which is unpacked via **). home.docker.run tokens are
        # appended verbatim AFTER the translated flags and BEFORE the image,
        # never translated to an --extra-args flag.
        return DockerRunner(config.image).run(args, extra_args=home.docker.run, **params)
    finally:
        # Step 13 — only the env-file is deleted; the persistent afm state
        # directory (runtime_dir) survives under EVERY exit path.
        if env_file is not None:
            env_file.unlink(missing_ok=True)

        signal.signal(signal.SIGTERM, prev_term)
        signal.signal(signal.SIGINT, prev_int)


def run_pipeline_container(  # noqa: PLR0913, PLR0917
    name: str,
    config: ProjectConfig,
    extra_env: tuple[str, ...] = (),
    proxy: str | None = None,
    hosts: dict[str, str] | None = None,
    clean: bool = False,
    update: bool = False,
    workflow: str | None = None,
    no_workflow: bool = False,
    profile: str | None = None,
    skip: tuple[str, ...] = (),
    parallel: int | None = None,
    home_profiles: dict[str, dict[str, Any]] | None = None,
    fail_on_error: bool = False,
) -> int:
    """Launch the goga Docker container to run ``python -m goga.pipeline``.

    Args:
        name: Pipeline name without extension.
        config: Loaded project configuration, consumed for the host-owned
            launch fields only (``image``, ``dockerfile``); the run-parameter
            fields (``pipeline.agent``, ``pipeline.env``) are consumed nowhere
            on the host — they resolve in-container.
        extra_env: Additional raw KEY=VALUE strings forwarded into the container
            env-file (e.g. agent authorization tokens supplied via the host-side
            ``-e/--env`` Click option). Default is empty.
        proxy: Resolved HTTP/HTTPS proxy URL (CLI overrides config in the
            caller). When non-None, the launcher writes ``HTTP_PROXY``,
            ``HTTPS_PROXY``, and ``NO_PROXY=localhost,127.0.0.1`` into the
            env-file.
        hosts: Resolved host→IP dict (CLI entries merged on top of
            ``config.pipeline.hosts`` by the caller). Each entry becomes a
            docker ``--add-host HOST:IP`` flag.
        clean: When True, wipe the persistent afm state host directory before
            launch via ``clean_pipeline_runtime_dir``.
        update: When True, refresh the image before launch via ``docker_update``
            (build when a project Dockerfile is declared, else pull). When False
            (default), skip the refresh.
        workflow: optional workflow name forwarded from the ``--workflow`` CLI
            flag. Appended to the in-container argv as ``-w <workflow>`` and
            carried by the ``GOGA_WORKFLOW`` engine line (file existence
            already validated by the caller).
        no_workflow: flag forwarded from the ``--no-workflow`` CLI flag.
            ``--no-workflow`` joins the in-container argv and no
            ``GOGA_WORKFLOW`` line is written; mutually exclusive with
            ``workflow`` (enforced by the caller).
        profile: optional profile name forwarded from the ``-p/--profile`` CLI
            flag — the CLI activation channel. Appended to the in-container
            argv as ``--profile <profile>`` ONLY when set; omitted when None
            (the ambient env channel and the workflow ``profile:`` default
            resolve in-container).
        skip: raw stage names forwarded from the repeatable ``-s/--skip`` CLI
            option (default empty). Each name appends one ``-s <name>`` to the
            in-container argv so the in-container ``run_pipeline`` routine
            applies ``apply_skip_stages`` over the resolved workflow; the host
            does NOT validate or dedup the names (validation is in-container).
        parallel: optional int (None when absent) capping concurrently executing
            stages, forwarded from the long-only ``--parallel`` CLI option.
            Appended to the in-container run argv as ``--parallel <parallel>``
            ONLY when not None (the in-container ``pipeline_cli`` forwards it
            to afm's ``--max-parallel``); omitted when None so afm runs
            unbounded (backward compatible). Not defaulted — None ⇒ unbounded.
            Distinct from the Docker ``-p <port>:<port>`` port-publish token.
        home_profiles: the loaded home bundle (the ``load_home_profiles``
            result of the caller, None when empty) — encoded into the
            ``GOGA_HOME_PROFILES`` engine line of the env-file only when
            non-empty (per ``home-profiles-carriage``; the whole bundle
            crosses because the effective profile name may only become known
            in-container).
        fail_on_error: the run-form fail-fast decision forwarded from the
            ``--fail-on-error`` CLI flag. Appended to the in-container run
            argv as ``--fail-on-error`` ONLY when True (the in-container
            ``pipeline_cli`` threads it onto the engine's ``--exit-on-fail``);
            False (default) omits the flag.

    Returns:
        The container's exit code.

    Raises:
        click.ClickException: When docker is missing, ``config.image`` is None,
            the home config file is malformed (a missing file is the normal
            no-op state), or a fatal image build is surfaced (D5).
        SystemExit: ``128 + signum`` when SIGTERM/SIGINT is received during run.

    Note:
        Home (machine-wide) config is loaded once up front on BOTH substrates
        — an absent file is the normal no-op state. The project is mounted at
        ``/workspace``; user pipelines are NOT bind-mounted from the host —
        the image is populated at build time via ``RUN goga connect ...`` in
        the Dockerfile, so the run operates entirely in-container. The
        workflow decision, the profile value, and the skip names travel to
        the container as argv flags; the ambient profile, the encoded home
        bundle, and the effective workflow name travel as env-file engine
        lines (each only when it carries cargo, under the engine-skip
        rule). The host prints NO workflow line — the launch feedback line
        prints in-container; the afm configuration file and the task env
        layer (``pipeline.env``) resolve in-container (the host resolves no
        agent and writes no afm configuration).

        Direct substrate (step 12a, ``is_in_docker`` True): every docker-hosted
        step is skipped — no docker-CLI check, no ``config.image`` guard, no
        host runtime-dir machinery, no env-file write, no image acquisition,
        no ``DockerRunner``. The port is still allocated on both substrates;
        the SAME ``_compose_env_lines`` ladder composes the env lines (parsed
        into the child env layer — no env-file exists, nothing to unlink) and
        the SAME ``_compose_run_args`` composes the argv, executed through
        ``run_direct`` (per ``direct-runner``): streamed output, forwarded
        SIGTERM/SIGINT (exit ``128 + signum`` — no caller-side D7 handler;
        ``run_direct`` owns the signals), the child's exit code verbatim.
        ``clean`` wipes the in-container AFM_DIR before launch; ``update``
        never reaches this branch (the caller rejected it).
    """
    # Step 1 — docker-CLI gate (host substrate only): inside the goga image
    # (the GOGA_DOCKER marker) there is no docker launch to check or acquire.
    if not is_in_docker() and not _check_docker():
        raise click.ClickException("docker not found in PATH")

    # Home (machine-wide) config preamble — an empty HomeConfig when the file is
    # absent (no-op). Loaded ONCE here and shared by both modes: home.env is the
    # run-mode env-file BASE layer (lowest priority); home.docker.run reaches
    # every docker run as a separate extra_args keyword; home.docker.build is
    # forwarded to image build (build branch only) in both modes. A malformed
    # home file surfaces as a clean ClickException per the click-wrapping
    # convention (absence is normal).
    try:
        home: HomeConfig = load_home_config()
    except (ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    # Step 12a — the direct substrate: execute the SAME composed argv and env
    # contract as a child of the current environment (one composition, two
    # sinks — the argv/env composers below are the ones the host path uses).
    if is_in_docker():
        # The port is part of the composed contract — allocated on BOTH
        # substrates (mirrors the docker -p publish of the host path).
        port = _allocate_port()

        # --clean wipes the in-container AFM_DIR before launch — never after,
        # and never in a finally (the directory survives across runs).
        if clean:
            afm_state = Path(_IN_CONTAINER_AFM_DIR)

            if afm_state.exists():
                shutil.rmtree(afm_state)

            afm_state.mkdir(parents=True, exist_ok=True)

        lines = _compose_env_lines(
            home_env=home.env,
            docker_run_tokens=home.docker.run,
            extra_env=extra_env,
            proxy=proxy,
            ambient_profile=os.environ.get("GOGA_PROFILE", ""),
            home_profiles=home_profiles,
            workflow_name=_resolve_workflow_env_name(workflow, no_workflow, name),
        )
        args = _compose_run_args(name, port, workflow, no_workflow, profile, skip, parallel, fail_on_error)

        # No env-file exists on this path (nothing to unlink) and no
        # caller-side D7 handler — run_direct owns the signals. The spawn
        # failure channel (D5): the executor propagates a raw OSError from
        # Popen; the caller owns the wrapping (clean message + exit 1).
        try:
            return run_direct(["python3", *args], env=_env_overlay(lines))
        except OSError as exc:
            raise click.ClickException(str(exc)) from exc

    if config.image is None:
        raise click.ClickException("image in .goga/config.yml is not set")

    container_name = f"goga-pipeline-{os.getpid()}"

    return _run_named(
        name,
        config,
        home,
        container_name,
        extra_env,
        proxy,
        hosts,
        clean,
        update,
        workflow,
        no_workflow,
        profile,
        skip,
        parallel,
        home_profiles,
        fail_on_error,
    )
