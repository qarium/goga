"""Host-side docker launcher for ``goga pipeline``.

Launches the goga Docker container to run ``python -m goga.pipeline`` in either
discovery (``name is None``) or run (``name`` provided) mode, and returns the
container's exit code. Mirrors the launcher shape of ``goga/commands/build``:
docker discovery, image pull, a SIGTERM/SIGINT handler that tears down the
container, and mandatory cleanup in ``finally``.

The runtime boundary to ``goga/pipeline`` is docker — this module imports no
Type from ``goga/pipeline``.
"""

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

from ...agents import resolve_credential_mounts, resolve_wrapper_path
from ...config import Config
from ...runtime import resolve_runtime_dir

logger = logging.getLogger(__name__)


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


def _pull_image(image: str) -> None:
    """Pull the image before launch; log a warning and continue on failure.

    Args:
        image: Docker image reference to pull.
    """
    result = subprocess.run(
        ["docker", "pull", image],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(f"failed to pull image '{image}'")


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


def _write_env_file(
    env: dict[str, str],
    extra_env: tuple[str, ...] = (),
) -> Path:
    """Write environment variables to a private temporary env file (mode 0600).

    Args:
        env: Mapping of environment variables to write as KEY=VALUE lines.
        extra_env: Additional raw KEY=VALUE strings to append verbatim, mirroring
            ``goga/commands/build._write_env_file``. No validation is performed —
            strings are written as-is, and later duplicates override earlier ones
            inside the container (the same semantics as the build command).

    Returns:
        Path to the written temporary file.
    """
    fd, path = tempfile.mkstemp(prefix="goga-pipeline-env-")
    with os.fdopen(fd, "w") as f:
        Path(path).chmod(stat.S_IRUSR | stat.S_IWUSR)
        for k, v in env.items():
            f.write(f"{k}={v}\n")
        for pair in extra_env:
            f.write(f"{pair}\n")
    return Path(path)


def _allocate_port() -> int:
    """Allocate a free localhost TCP port by binding to an ephemeral port.

    Binds a socket to ``("", 0)``, reads the assigned port, and closes the
    socket. A small race window is accepted: the port may be reused before the
    container binds it.

    Returns:
        The allocated port number.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _write_afm_config_tmpfile(wrapper_path: str) -> Path:
    """Write the afm ``client.command`` config to a private temp file (mode 0600).

    The file is created in the system temp directory — NEVER under ``/workspace``
    (per ``[[feedback_workspace_is_project_only]]``). It is mounted read-only at
    ``/home/goga/.afm/config.yaml`` inside the container.

    Args:
        wrapper_path: The resolved absolute in-container wrapper script path
            (``resolve_wrapper_path(config.pipeline.agent)``), e.g.
            ``/home/goga/bin/codex-as-claude.sh``. Written verbatim into
            ``client.command`` — never a bare agent name.

    Returns:
        Path to the written temporary file.
    """
    fd, path = tempfile.mkstemp(prefix="goga-afm-config-")
    with os.fdopen(fd, "w") as f:
        Path(path).chmod(stat.S_IRUSR | stat.S_IWUSR)
        f.write(f"client.command: {wrapper_path}\n")
    return Path(path)


def _build_discovery_cmd(
    image: str,
    container_name: str,
    hosts: dict[str, str] | None = None,
) -> list[str]:
    """Assemble the discovery-mode docker command (``-m goga.pipeline list``).

    Mounts the project at ``/workspace``. User pipelines are NOT bind-mounted
    from the host: the image is populated at build time via
    ``RUN goga connect ...`` in the Dockerfile, so ``/home/goga/.goga/pipelines``
    inside the container reflects the image's user pipelines and discovery runs
    entirely in-container.

    Args:
        image: Docker image to run.
        container_name: Name assigned to the container via ``--name``.
        hosts: Resolved host→IP mapping (config.pipeline.hosts merged with parsed
            ``--add-host`` CLI entries by the caller). Each pair becomes a
            ``--add-host HOST:IP`` flag. ``None`` adds no host entries.

    Returns:
        The full docker command as a list of string arguments.
    """
    if hosts is None:
        hosts = {}

    project_dir = Path.cwd().resolve()
    cmd: list[str] = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "-v",
        f"{project_dir}:/workspace",
        "-w",
        "/workspace",
    ]
    for host, ip in hosts.items():
        cmd.extend(["--add-host", f"{host}:{ip}"])
    cmd.extend(
        [
            "--entrypoint",
            "python3",
            image,
            "-m",
            "goga.pipeline",
            "list",
        ]
    )
    return cmd


def _build_run_cmd(  # noqa: PLR0913
    image: str,
    container_name: str,
    port: int,
    name: str,
    afm_config: Path,
    env_file: Path,
    runtime_dir: Path,
    hosts: dict[str, str] | None = None,
) -> list[str]:
    """Assemble the run-mode docker command.

    Builds ``docker run ... -m goga.pipeline run <name> --port <port>`` with the
    project mounted at ``/workspace``, the persistent afm state host directory
    mounted read-write at ``/home/goga/pipeline`` (so afm state survives across
    runs of the same pipeline in the same project on the same branch), the
    afm-config tmpfile mounted read-only at the FIXED path
    ``/home/goga/.afm/config.yaml`` (independent of AFM_DIR — see the ``afm``
    practice), the env-file, the published port, ``--add-host`` entries, and a
    read-only bind-mount for every credential file returned by
    ``resolve_credential_mounts()``. User pipelines are NOT bind-mounted from
    the host: the image is populated at build time via ``RUN goga connect ...``
    in the Dockerfile, so ``/home/goga/.goga/pipelines`` inside the container
    reflects the image's user pipelines.

    Args:
        image: Docker image to run.
        container_name: Name assigned to the container via ``--name``.
        port: Port published on both sides (``-p <port>:<port>`` and ``--port``).
        name: Pipeline name forwarded as the ``run`` positional argument.
        afm_config: Host path to the afm-config tmpfile.
        env_file: Host path to the env file mounted via ``--env-file``.
        runtime_dir: Host path to the persistent afm state directory, mounted
            read-write at ``/home/goga/pipeline``. Created by the caller; never
            deleted here.
        hosts: Resolved host→IP mapping (config.pipeline.hosts merged with parsed
            ``--add-host`` CLI entries by the caller). Each pair becomes a
            ``--add-host HOST:IP`` flag. ``None`` adds no host entries.

    Returns:
        The full docker command as a list of string arguments.
    """
    if hosts is None:
        hosts = {}

    project_dir = Path.cwd().resolve()
    cmd: list[str] = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "-p",
        f"{port}:{port}",
        "-v",
        f"{project_dir}:/workspace",
        "-w",
        "/workspace",
        # persistent afm state: read-write so afm can persist flows/run-state;
        # survives across runs. NEVER deleted by the launcher.
        "-v",
        f"{runtime_dir}:/home/goga/pipeline",
        # client.command overlay: read-only, FIXED target independent of AFM_DIR.
        "-v",
        f"{afm_config}:/home/goga/.afm/config.yaml:ro",
        "--env-file",
        str(env_file),
    ]

    for host, ip in hosts.items():
        cmd.extend(["--add-host", f"{host}:{ip}"])

    # Credential mounts: agent-agnostic. Every tuple from
    # resolve_credential_mounts() is an existing file — no re-check needed.
    for host_path, container_path in resolve_credential_mounts():
        cmd.extend(["-v", f"{host_path}:{container_path}:ro"])

    cmd.extend(
        [
            "--entrypoint",
            "python3",
            image,
            "-m",
            "goga.pipeline",
            "run",
            name,
            "--port",
            str(port),
        ]
    )
    return cmd


def _on_signal(signum: int, _frame: object) -> None:
    """SIGTERM/SIGINT handler that unwinds to the ``finally`` cleanup.

    Raising ``SystemExit(128 + signum)`` propagates out of ``proc.wait()`` and
    triggers the ``finally`` block, which runs ``docker kill`` and restores the
    previous handlers. This mirrors ``goga/commands/build.build`` and keeps the
    handler itself free of subprocess calls (signal handlers should stay minimal).
    """
    raise SystemExit(128 + signum)


def resolve_pipeline_runtime_dir(pipeline_name: str) -> Path:
    """Compute the persistent afm state host directory for a pipeline.

    Thin facade over :func:`resolve_runtime_dir`: delegates the path composition
    (current project path, current git branch, and ``pipeline_name``) so that
    afm state survives across runs of the same pipeline in the same project on
    the same branch. Pure with respect to the filesystem — the directory is NOT
    created here (creation is the caller's responsibility).

    Args:
        pipeline_name: Pipeline name without extension (the run-mode name arg).

    Returns:
        Absolute host path
        ``~/.goga/runtime/pipelines/<normalized>/<branch>/<pipeline_name>``.
    """
    return resolve_runtime_dir("pipelines", pipeline_name)


def clean_pipeline_runtime_dir(pipeline_runtime_dir: Path) -> None:
    """Recursively wipe and recreate the persistent afm state directory.

    Called before container launch when ``--clean`` is set. Idempotent: when the
    directory does not exist it is simply created; repeated calls on an
    already-clean directory do not raise. A ``FileNotFoundError`` from the
    removal is tolerated so a directory that vanishes between the existence
    check and the ``rmtree`` — e.g. a concurrent ``goga pipeline --clean`` on the
    same project/branch/name — does not raise. Any other failure (e.g. a
    permission error on a file written under a different UID by a prior
    container run) propagates: per the CODEMANIFEST constraint the wipe must be
    total, so a partial removal surfaces as an error rather than silently
    leaving stale state mounted into the next run.

    Args:
        pipeline_runtime_dir: Host path computed by
            :func:`resolve_pipeline_runtime_dir`.
    """
    if pipeline_runtime_dir.exists():
        # Tolerate a directory that vanishes between the check and rmtree (a
        # concurrent --clean); any other failure propagates — the wipe is total.
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(pipeline_runtime_dir)
    pipeline_runtime_dir.mkdir(parents=True, exist_ok=True)


def _run_discovery(
    config: Config,
    container_name: str,
    hosts: dict[str, str] | None,
    update: bool,
) -> int:
    """Launch the container in discovery mode (``-m goga.pipeline list``).

    Discovery honours ``hosts`` (``--add-host`` flags) and ``update``
    (conditional image pull), and ignores ``extra_env``, ``proxy``, and
    ``clean`` — no env-file is written and no afm state directory is involved.

    Args:
        config: Loaded project configuration (provides ``image``).
        container_name: Name assigned to the container.
        hosts: Resolved host→IP mapping forwarded as ``--add-host`` flags.
        update: When True, pull the image before launch (warning on failure).

    Returns:
        The container's exit code.
    """
    prev_term = signal.signal(signal.SIGTERM, _on_signal)
    prev_int = signal.signal(signal.SIGINT, _on_signal)
    try:
        cmd = _build_discovery_cmd(config.image, container_name, hosts)
        if update:
            _pull_image(config.image)
        proc = subprocess.Popen(cmd)
        return proc.wait()
    finally:
        subprocess.run(
            ["docker", "kill", container_name],
            check=False,
            capture_output=True,
        )
        signal.signal(signal.SIGTERM, prev_term)
        signal.signal(signal.SIGINT, prev_int)


def _run_named(  # noqa: PLR0913
    name: str,
    config: Config,
    container_name: str,
    extra_env: tuple[str, ...],
    proxy: str | None,
    hosts: dict[str, str] | None,
    clean: bool,
    update: bool,
) -> int:
    """Launch the container in run mode (``-m goga.pipeline run <name> --port``).

    Run mode allocates a free port, writes a private afm-config tmpfile, ensures
    the persistent afm state host directory exists (wiping it first when
    ``clean`` is set), writes a private env-file combining
    ``config.pipeline.env``, git identity, ``extra_env``, ``AFM_DIR``, and — when
    ``proxy`` is set — the proxy env vars, prints the Web UI URL, optionally
    pulls the image, and runs the container. The persistent directory is created
    before launch and never deleted in ``finally`` (it survives across runs and
    across the signal-exit path).

    Args:
        name: Pipeline name without extension.
        config: Loaded project configuration.
        container_name: Name assigned to the container.
        extra_env: Additional raw KEY=VALUE strings forwarded into the container
            env-file (e.g. agent authorization tokens).
        proxy: Resolved HTTP/HTTPS proxy URL. When non-None, populates
            ``HTTP_PROXY``/``HTTPS_PROXY``/``NO_PROXY`` in the env-file.
        hosts: Resolved host→IP mapping forwarded as ``--add-host`` flags.
        clean: When True, wipe the persistent afm state directory before launch.
        update: When True, pull the image before launch (warning on failure).

    Returns:
        The container's exit code.
    """
    port = _allocate_port()

    # Resolve the persistent afm state host directory and ensure it exists
    # BEFORE installing signal handlers or creating temp files: it must be on
    # disk and survive every exit path (including the signal-exit path), and the
    # optional --clean wipe happens here — strictly before launch, never after.
    runtime_dir = resolve_pipeline_runtime_dir(name)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        clean_pipeline_runtime_dir(runtime_dir)

    # Install the SIGTERM/SIGINT handlers before creating temp files so any
    # exception (or signal) raised during setup propagates through the finally
    # below, which unlinks the temp files. Creating them before this try block
    # would leak them — the env file carries git identity and pipeline secrets.
    prev_term = signal.signal(signal.SIGTERM, _on_signal)
    prev_int = signal.signal(signal.SIGINT, _on_signal)
    afm_config: Path | None = None
    env_file: Path | None = None
    try:
        wrapper_path = resolve_wrapper_path(config.pipeline.agent)
        afm_config = _write_afm_config_tmpfile(wrapper_path)
        git_env = _read_git_config()
        env = {**git_env, **config.pipeline.env}
        # AFM_DIR redirects afm state (flows, run-state) to the rw-mounted
        # persistent directory at /home/goga/pipeline; ~/.afm/config.yaml stays
        # the config source regardless (see the `afm` practice).
        env["AFM_DIR"] = "/home/goga/pipeline"
        if proxy is not None:
            env["HTTP_PROXY"] = proxy
            env["HTTPS_PROXY"] = proxy
            env["NO_PROXY"] = "localhost,127.0.0.1"
        env_file = _write_env_file(env, extra_env)
        click.echo(f"Web UI: http://localhost:{port}")
        cmd = _build_run_cmd(
            config.image,
            container_name,
            port,
            name,
            afm_config,
            env_file,
            runtime_dir,
            hosts,
        )
        if update:
            _pull_image(config.image)
        proc = subprocess.Popen(cmd)
        return proc.wait()
    finally:
        # Only the tmpfile and env-file are deleted — the persistent afm state
        # directory (runtime_dir) survives under EVERY exit path.
        if afm_config is not None:
            afm_config.unlink(missing_ok=True)
        if env_file is not None:
            env_file.unlink(missing_ok=True)
        subprocess.run(
            ["docker", "kill", container_name],
            check=False,
            capture_output=True,
        )
        signal.signal(signal.SIGTERM, prev_term)
        signal.signal(signal.SIGINT, prev_int)


def run_pipeline_container(  # noqa: PLR0913
    name: str | None,
    config: Config,
    extra_env: tuple[str, ...] = (),
    proxy: str | None = None,
    hosts: dict[str, str] | None = None,
    clean: bool = False,
    update: bool = False,
) -> int:
    """Launch the goga Docker container to run ``python -m goga.pipeline``.

    Discovery mode (``name is None``) runs ``-m goga.pipeline list`` and ignores
    ``extra_env``, ``proxy``, and ``clean`` — it honours only ``hosts``
    (``--add-host`` flags) and ``update`` (conditional image pull); no env-file
    is written and no afm state directory is involved.

    Run mode (``name`` provided) allocates a free port, writes a private
    afm-config tmpfile (``client.command: <resolved wrapper path>`` — the
    absolute ``resolve_wrapper_path(config.pipeline.agent)`` value, never a bare
    agent name) mounted read-only at the FIXED path
    ``/home/goga/.afm/config.yaml``, ensures the persistent afm state host
    directory exists (wiping it first when ``clean`` is set), writes a private
    env-file combining ``config.pipeline.env``, git identity, ``extra_env`` (raw
    KEY=VALUE strings), ``AFM_DIR=/home/goga/pipeline``, and — when ``proxy`` is
    set — the proxy env vars, mounts the persistent directory read-write at
    ``/home/goga/pipeline`` (it survives across runs and the signal-exit path),
    adds ``--add-host`` flags from ``hosts``, mounts every credential file from
    ``resolve_credential_mounts()`` read-only, optionally pulls the image, prints
    the Web UI URL, and runs ``-m goga.pipeline run <name> --port <port>``.

    Both modes mount the project at ``/workspace``. User pipelines are NOT
    bind-mounted from the host: the image is populated at build time via
    ``RUN goga connect ...`` in the Dockerfile, so ``/home/goga/.goga/pipelines``
    inside the container reflects the image's user pipelines and discovery/run
    operate entirely in-container.

    Args:
        name: Pipeline name without extension. ``None`` selects discovery mode.
        config: Loaded project configuration (provides ``image``,
            ``pipeline.agent``, ``pipeline.env``).
        extra_env: Additional raw KEY=VALUE strings forwarded into the container
            env-file in run mode (e.g. agent authorization tokens supplied via
            the host-side ``-e/--env`` Click option). Default is empty. Ignored
            in discovery mode (``name is None``), which never writes an env-file.
        proxy: Resolved HTTP/HTTPS proxy URL (CLI overrides config in the
            caller). When non-None in run mode, the launcher writes
            ``HTTP_PROXY``, ``HTTPS_PROXY``, and ``NO_PROXY=localhost,127.0.0.1``
            into the env-file. Ignored in discovery mode.
        hosts: Resolved host→IP dict (CLI entries merged on top of
            ``config.pipeline.hosts`` by the caller). Each entry becomes a
            docker ``--add-host HOST:IP`` flag. Effective in both modes.
        clean: When True in run mode, wipe the persistent afm state host
            directory before launch via ``clean_pipeline_runtime_dir``. No-op in
            discovery mode.
        update: When True, pull the image before launch (failure is a warning,
            not fatal). When False (default), skip the pull. Effective in both
            modes.

    Returns:
        The container's exit code.

    Raises:
        click.ClickException: When docker is missing or ``config.image`` is None.
        SystemExit: ``128 + signum`` when SIGTERM/SIGINT is received during run.
    """
    if not _check_docker():
        raise click.ClickException("docker not found in PATH")

    if config.image is None:
        raise click.ClickException("image in .goga/config.yml is not set")

    container_name = f"goga-pipeline-{os.getpid()}"

    if name is None:
        return _run_discovery(config, container_name, hosts, update)

    return _run_named(
        name,
        config,
        container_name,
        extra_env,
        proxy,
        hosts,
        clean,
        update,
    )
