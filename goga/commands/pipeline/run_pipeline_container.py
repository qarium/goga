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

import click
import yaml

from ...config import HomeConfig, ProjectConfig, load_home_config
from ...docker import DockerRunner, docker_build_if_not_exist, docker_update, encode_extra_env
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


def _resolve_workflow_log_name(
    workflow: str | None,
    no_workflow: bool,
    name: str,
) -> str | None:
    """Compute the workflow log name (host-side, log-only decision).

    Args:
        workflow: optional workflow name from the ``--workflow`` CLI flag.
        no_workflow: flag from the ``--no-workflow`` CLI flag.
        name: pipeline name without extension (the auto-match basename).

    Returns:
        The name to surface in the workflow log line, or ``None`` when no
        workflow will be applied and no log should be emitted —
        ``no_workflow is True`` → ``None`` (workflow application is
        disabled); ``workflow is not None`` (explicit ``--workflow``, file
        already validated by the caller) → ``workflow``; else the
        auto-match fallback ``<cwd>/.goga/workflows/<name>.yml`` — ``name``
        when it exists (the in-container routine resolves the basename
        fallback itself, so the argv carries neither workflow flag), or
        ``None`` when absent (in-container silent-miss, no log).

    Note:
        Workflow paths are project-only — resolved from ``Path.cwd()``
        (which is ``/workspace`` in-container), mirroring the in-container
        resolution. The decision produces no env entry: the workflow flags
        travel to the container as argv, and this helper only decides
        whether the workflow log line is emitted and what it names.
    """
    if no_workflow:
        return None
    if workflow is not None:
        return workflow

    # Auto-match fallback: the basename workflow-file is resolved in-container,
    # so the argv carries neither workflow flag. The host only checks existence
    # to decide whether the workflow log line is accurate (the file will
    # actually apply). Workflow paths are project-only (CODEMANIFEST step 6b) —
    # mirroring the explicit-``--workflow`` and in-container containment
    # guards, a ``name`` carrying a ``..`` segment or an absolute prefix that
    # escapes the workflows dir is a silent miss (``None``, no log line), never
    # a path resolved into the wider filesystem. The in-container resolver
    # re-applies the same containment before parsing, so this only keeps the
    # host log line honest.
    workflows_root = (Path.cwd() / ".goga" / "workflows").resolve()
    auto_match_path = workflows_root / f"{name}.yml"

    try:
        auto_match_path.resolve().relative_to(workflows_root)
    except ValueError:
        return None

    if auto_match_path.exists():
        return name

    return None


def _build_env_file(
    home_env: dict[str, str],
    docker_run_tokens: list[str],
    extra_env: tuple[str, ...],
    proxy: str | None,
) -> Path:
    """Build the run-mode env-file (Algorithm step 10) — environment layers only.

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

    Returns:
        Path to the written private env-file.

    Note:
        Ladder order (lowest to highest): ``home_env`` as the BASE layer
        under git identity, the raw ``extra_env`` lines, the engine
        variables (``AFM_DIR``, ``AFM_DOCKER_FILE_ROOTS``, and the proxy
        triple when ``proxy`` is set), and the ``GOGA_EXTRA_ENV`` payload
        line last — docker ``--env-file`` last-write-wins gives it
        precedence over any CLI line of the same key (a user-supplied
        ``GOGA_*`` string is written verbatim; the launcher-written payload
        line still wins). An engine key the CLI explicitly supplied is
        SKIPPED — the raw CLI line keeps winning without a duplicate
        launcher line (the documented ``-e AFM_DOCKER_FILE_ROOTS=...`` /
        ``-e HTTP_PROXY=...`` escape hatch). The task env layer
        (``config.pipeline.env``) and all run-coordination state (the
        workflow decision, the skip names) NEVER enter the env-file — they
        apply in-container / travel as argv.
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
    # every launch. Last line, so last-write-wins gives it precedence over any
    # CLI line of the same key.
    lines.append(f"GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}")

    return _write_env_file(lines)


def _compose_run_args(  # noqa: PLR0913, PLR0917
    name: str,
    port: int,
    workflow: str | None,
    no_workflow: bool,
    skip: tuple[str, ...],
    parallel: int | None,
) -> list[str]:
    """Compose the in-container run argv (Algorithm step 11 — the argv channel).

    Args:
        name: Pipeline name without extension.
        port: The allocated localhost port (mirrors the docker ``-p`` publish).
        workflow: optional workflow name from the ``--workflow`` CLI flag.
        no_workflow: flag from the ``--no-workflow`` CLI flag.
        skip: raw stage names from the repeatable ``-s/--skip`` CLI option.
        parallel: optional int capping concurrently executing stages.

    Returns:
        The post-image command handed to ``DockerRunner.run``:
        ``["-m","goga.pipeline","run",<name>,"--port",<port>]`` followed,
        in order, by the workflow decision (``-w <workflow>`` when
        explicit, else ``--no-workflow`` when set, else neither flag — the
        in-container run coordination attempts the basename auto-match
        fallback itself), then one ``-s <name>`` per skip entry (forwarded
        as parsed — no validation, no dedup; unknown names are the
        in-container compiler's structural error), then ``--parallel
        <parallel>`` only when not None.
    """
    args = ["-m", "goga.pipeline", "run", name, "--port", str(port)]

    # The workflow decision travels as argv, exactly as given: -w <workflow>
    # when explicit, else --no-workflow when set, else neither flag. The elif
    # keeps the assembly total even though the caller rejects the combination.
    if workflow is not None:
        args += ["-w", workflow]
    elif no_workflow:
        args += ["--no-workflow"]

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
    skip: tuple[str, ...] = (),
    parallel: int | None = None,
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
            in-container argv as ``-w <workflow>`` and named by the workflow log
            line. The file existence was already validated by the caller.
        no_workflow: flag from ``--no-workflow``. When True, ``--no-workflow``
            joins the in-container argv and no workflow log line is emitted
            (mutually exclusive with ``workflow``, enforced by caller).
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
        restoring it); compute the workflow log decision and emit the log
        line; write the env-file (environment layers only); assemble the
        in-container argv with the workflow decision and skip names as
        flags; optionally refresh the image via ``docker_update``
        (forwarding ``home.docker.build`` to image build in the build
        branch only); run the container via ``DockerRunner`` (forwarding
        ``home.docker.run`` as the separate ``extra_args`` keyword). The
        persistent directory is never deleted in ``finally`` — only the
        env-file is unlinked.
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
        # Step 8 — the workflow log decision (host-side, BEFORE launch).
        # Log-only: it produces no env entry and no argv flag; the flags below
        # come from the raw parameters.
        workflow_log_name = _resolve_workflow_log_name(workflow, no_workflow, name)
        # Step 9 — the workflow log line. Emitted ONLY when a workflow will
        # actually be applied (explicit --workflow, or basename auto-match file
        # present on the host). The only host-side stdout besides the docker
        # output stream.
        if workflow_log_name is not None:
            click.echo(f'Pipeline running with workflow "{workflow_log_name}"')

        # Step 10 — the env-file carries environment layers ONLY.
        env_file = _build_env_file(
            home_env=home.env,
            docker_run_tokens=home.docker.run,
            extra_env=extra_env,
            proxy=proxy,
        )

        project_dir = Path.cwd().resolve()
        # Step 11 — mounts: the project as /workspace (container working dir)
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
        args = _compose_run_args(name, port, workflow, no_workflow, skip, parallel)
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

        # Step 12 — first-run safety net: build the local image if it is absent
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

        # Step 13 — the --update refresh.
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

        # Step 14 — extra_args is a SEPARATE keyword to DockerRunner.run (NOT
        # part of params, which is unpacked via **). home.docker.run tokens are
        # appended verbatim AFTER the translated flags and BEFORE the image,
        # never translated to an --extra-args flag.
        return DockerRunner(config.image).run(args, extra_args=home.docker.run, **params)
    finally:
        # Step 15 — only the env-file is deleted; the persistent afm state
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
    skip: tuple[str, ...] = (),
    parallel: int | None = None,
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
            named by the workflow log line (file existence already validated by
            the caller).
        no_workflow: flag forwarded from the ``--no-workflow`` CLI flag.
            ``--no-workflow`` joins the in-container argv and no workflow log
            line is emitted; mutually exclusive with ``workflow`` (enforced by
            the caller).
        skip: raw stage names forwarded from the repeatable ``-s/--skip`` CLI
            option (default empty). Each name appends one ``-s <name>`` to the
            in-container argv so the in-container ``run_pipeline`` routine
            applies ``apply_skip_stages`` over the resolved workflow; the host
            does NOT validate or dedup the names (validation is in-container).
        parallel: optional int (None when absent) capping concurrently executing
            stages, forwarded from the ``-p/--parallel`` CLI option. Appended to
            the in-container run argv as ``--parallel <parallel>`` ONLY when not
            None (the in-container ``pipeline_cli`` forwards it to afm's
            ``--max-parallel``); omitted when None so afm runs unbounded
            (backward compatible). Not defaulted — None ⇒ unbounded. Distinct
            from the Docker ``-p <port>:<port>`` port-publish token.

    Returns:
        The container's exit code.

    Raises:
        click.ClickException: When docker is missing, ``config.image`` is None,
            the home config file is malformed (a missing file is the normal
            no-op state), or a fatal image build is surfaced (D5).
        SystemExit: ``128 + signum`` when SIGTERM/SIGINT is received during run.

    Note:
        Home (machine-wide) config is loaded once up front — an absent file
        is the normal no-op state. The project is mounted at ``/workspace``;
        user pipelines are NOT bind-mounted from the host — the image is
        populated at build time via ``RUN goga connect ...`` in the
        Dockerfile, so the run operates entirely in-container. The workflow
        decision and the skip names travel to the container as argv flags —
        the env-file never carries run-coordination state; the afm
        configuration file and the task env layer (``pipeline.env``)
        resolve in-container (the host resolves no agent and writes no afm
        configuration).
    """
    if not _check_docker():
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
        skip,
        parallel,
    )
