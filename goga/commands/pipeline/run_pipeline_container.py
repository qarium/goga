"""Host-side docker launcher for ``goga pipeline``.

Launches the goga Docker container to run ``python -m goga.pipeline`` in either
discovery (``name is None``) or run (``name`` provided) mode, and returns the
container's exit code. Image acquisition (``--update``) delegates to
``docker_update`` (build when a project Dockerfile is declared, else pull) and
container launch delegates to ``DockerRunner``, which owns the SIGTERM/SIGINT
lifecycle and the guaranteed ``docker kill``. Run mode installs its own
SIGTERM/SIGINT handler BEFORE writing the secret tmpfile/env-file (D7) — so a
signal during the setup window, including the ``docker_update`` build, unwinds
to the caller ``finally`` and unlinks the secret files. Discovery mode writes no
secret files, so it installs no caller-side handler (only the runner's applies).

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
import yaml

from ...agents import resolve_credential_mounts, resolve_wrapper_path
from ...config import HomeConfig, ProjectConfig, load_home_config
from ...docker import DockerRunner, docker_build_if_not_exist, docker_update
from ...runtime import resolve_runtime_dir

logger = logging.getLogger(__name__)

# The in-container path afm state is mounted on and ``AFM_DIR`` points at. The
# ``prompts_dir`` written into the afm-config tmpfile is derived from this same
# constant so the four agent prompts are written (by ``run_pipeline``) and read
# (by afm) at the same location — keeping a single source of truth rather than
# three independent literals that could silently diverge.
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
    """Write the afm config overlay to a private temp file (mode 0600).

    The file is created in the system temp directory — NEVER under ``/workspace``
    (per ``[[feedback_workspace_is_project_only]]``). It is mounted read-only at
    ``/home/goga/.afm/config.yaml`` inside the container.

    The overlay carries five static launcher-side fields:

    - ``client.command: <wrapper_path>`` — the resolved absolute in-container
      wrapper path afm will drive as the agent client. ``client`` is a nested
      YAML map (``client:`` + ``  command: <wrapper_path>``), NOT a flat
      dotted-key, because afm reads it as a YAML map (same as ``proxy``).
    - ``theme: goga`` — the dashboard theme applied by afm.
    - ``open_browser: false`` — the dashboard is reached via the
      host-printed ``http://localhost:<port>`` URL; afm must not attempt to
      open a browser inside the container.
    - ``proxy.enabled: false`` — disables afm's own internal outbound proxy
      provider. goga manages the outbound proxy through the container
      env-file (``HTTP_PROXY``/``HTTPS_PROXY``/``NO_PROXY``); afm's
      config-level proxy must stay off so the two layers never collide.
      ``proxy`` is a nested YAML map (``proxy:`` + ``  enabled: false``), NOT
      a flat dotted-key, because afm reads it as a YAML map.
    - ``prompts_dir: /home/goga/pipeline/prompts`` — where afm reads the four
      agent prompt files (``planning``/``implementation``/``review``/
      ``summary``) that ``run_pipeline`` materializes in-container. Fixed to
      the value derived from the ``AFM_DIR=/home/goga/pipeline`` constant —
      NOT derived from CLI or config (goga does not duplicate afm-owned
      settings in its own configuration).

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
        f.write("client:\n")
        f.write(f"  command: {wrapper_path}\n")
        f.write("theme: goga\n")
        f.write("open_browser: false\n")
        f.write("proxy:\n")
        f.write("  enabled: false\n")
        f.write(f"prompts_dir: {_IN_CONTAINER_AFM_DIR}/prompts\n")
    return Path(path)


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
    config: ProjectConfig,
    home: HomeConfig,
    container_name: str,
    hosts: dict[str, str] | None,
    update: bool,
) -> int:
    """Launch the container in discovery mode (``-m goga.pipeline list``).

    Discovery honours ``hosts`` (``--add-host`` flags) and ``update``
    (image refresh via ``docker_update``), and ignores ``extra_env``, ``proxy``,
    ``clean``, ``workflow``, ``no_workflow``, and ``skip`` — no env-file is
    written and no afm state directory is involved. ``home.env`` is therefore
    NOT applied here (no env-file); ``home.docker.run`` is forwarded to
    ``DockerRunner.run`` as the separate ``extra_args`` keyword, and
    ``home.docker.build`` is forwarded to ``docker_build_if_not_exist`` and
    ``docker_update`` (build branch only). Discovery writes no secret files,
    so it installs NO caller-side SIGTERM/SIGINT handler: only the runner's
    handler applies (it performs the guaranteed ``docker kill`` and restores
    the previous handlers).

    Args:
        config: Loaded project configuration (provides ``image``, ``dockerfile``).
        home: Loaded machine-wide home config. ``home.env`` is ignored in
            discovery (no env-file is written); ``home.docker.run`` is forwarded
            to ``DockerRunner.run`` as ``extra_args``; ``home.docker.build`` is
            forwarded to image build (build branch only).
        container_name: Name assigned to the container.
        hosts: Resolved host→IP mapping forwarded as ``--add-host`` flags.
        update: When True, refresh the image before launch via ``docker_update``
            (build when a Dockerfile is declared, else pull).

    Returns:
        The container's exit code.
    """
    project_dir = Path.cwd().resolve()
    mounts = [f"{project_dir}:/workspace"]

    # args = the post-image command (the in-container goga.pipeline list call);
    # params = the docker-run options the runner translates to flags via the
    # shared param→flag rule.
    args = ["-m", "goga.pipeline", "list"]
    params = {
        "name": container_name,
        "rm": True,
        "entrypoint": "python3",
        "workdir": "/workspace",
        "v": mounts,
        "add_host": [f"{host}:{ip}" for host, ip in (hosts or {}).items()],
    }

    # First-run safety net: build the local image if it is absent and a project
    # Dockerfile is declared. No-op when the image exists or no Dockerfile is
    # set. Fatal build surfaces as ClickException (D5 — clean message + exit 1).
    # Discovery writes no secret files, so no D7 caller-side handler applies.
    # home.docker.build is forwarded to image build (build branch only).
    try:
        docker_build_if_not_exist(config.image, config.dockerfile, extra_args=home.docker.build)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if update:
        # docker_update owns the build-vs-pull branch (build when a project
        # Dockerfile is declared — fatal; else pull — WARNING, non-fatal). D5: a
        # fatal build surfaces as a clean message + exit 1 rather than a
        # traceback; pull-branch failures stay a WARNING inside docker_pull.
        # home.docker.build forwarded in the build branch only (ignored on pull).
        try:
            docker_update(config.image, config.dockerfile, extra_args=home.docker.build)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

    # extra_args is a SEPARATE keyword to DockerRunner.run (NOT part of params,
    # which is unpacked via **). home.docker.run tokens are appended verbatim
    # AFTER the translated flags and BEFORE the image, never translated to an
    # --extra-args flag. Discovery applies NO env-file, so home.env is unused.
    return DockerRunner(config.image).run(args, extra_args=home.docker.run, **params)


def _resolve_workflow_env(
    workflow: str | None,
    no_workflow: bool,
    name: str,
) -> tuple[dict[str, str], str | None]:
    """Compute the workflow env-file entries and the workflow log name (host-side).

    Implements ``run_pipeline_container`` Algorithm step 9 — the host-side
    decision matrix taken BEFORE container launch so the workflow log line is
    accurate. Returns a 2-tuple ``(workflow_env, workflow_log_name)``:

    - ``no_workflow is True`` → ``({"GOGA_WORKFLOW_DISABLED": "1"}, None)`` — the
      in-container ``run_pipeline`` skips workflow resolution entirely; no log.
    - ``workflow is not None`` (explicit ``--workflow``, file already validated
      by the caller) → ``({"GOGA_WORKFLOW_NAME": workflow}, workflow)`` — the
      in-container routine parses that exact file; the log names it.
    - else (auto-match fallback) → compose ``<cwd>/.goga/workflows/<name>.yml``:
      when it exists, ``({}, name)`` (the in-container routine resolves the
      basename fallback itself, so NO env var is written — only the log names
      it); when absent, ``({}, None)`` (in-container silent-miss, no log).

    Workflow paths are project-only — resolved from ``Path.cwd()`` (which is
    ``/workspace`` in-container), mirroring the in-container resolution. The host
    never parses a workflow-file here; it only decides which env var (if any) to
    write and whether a workflow will actually be applied.

    Args:
        workflow: optional workflow name from the ``--workflow`` CLI flag.
        no_workflow: flag from the ``--no-workflow`` CLI flag.
        name: pipeline name without extension (the auto-match basename).

    Returns:
        ``(workflow_env, workflow_log_name)`` — the env-file entries to write
        and the name to surface in the workflow log line (or ``None`` when no
        workflow will be applied and no log should be emitted).
    """
    if no_workflow:
        return {"GOGA_WORKFLOW_DISABLED": "1"}, None
    if workflow is not None:
        return {"GOGA_WORKFLOW_NAME": workflow}, workflow

    # Auto-match fallback: the basename workflow-file is resolved in-container,
    # so the host writes NO workflow env var. It only checks existence to decide
    # whether the workflow log line is accurate (the file will actually apply).
    # Workflow paths are project-only (CODEMANIFEST step 6b) — mirroring the
    # explicit-``--workflow`` and in-container containment guards, a ``name``
    # carrying a ``..`` segment or an absolute prefix that escapes the workflows
    # dir is a silent miss (``workflow_log_name=None``, no log line), never a
    # path resolved into the wider filesystem. The in-container resolver re-applies
    # the same containment before parsing, so this only keeps the host log line
    # honest.
    workflows_root = (Path.cwd() / ".goga" / "workflows").resolve()
    auto_match_path = workflows_root / f"{name}.yml"
    try:
        auto_match_path.resolve().relative_to(workflows_root)
    except ValueError:
        return {}, None
    if auto_match_path.exists():
        return {}, name
    return {}, None


def _build_env_file(  # noqa: PLR0913, PLR0917
    home_env: dict[str, str],
    extra_env: tuple[str, ...],
    pipeline_env: dict[str, str],
    proxy: str | None,
    workflow: str | None,
    no_workflow: bool,
    name: str,
    skip: tuple[str, ...] = (),
) -> Path:
    """Build the run-mode env-file (Algorithm steps 9-11) and emit the workflow log line.

    Layers ``home_env`` (``home.env``) as the BASE (lowest-priority) env layer,
    then git identity, then ``pipeline_env`` (config.pipeline.env — project
    config wins over both git and home on key conflict), then ``AFM_DIR``, the
    proxy env vars (when ``proxy`` is set), and the workflow env vars per the
    decision matrix (``_resolve_workflow_env`` — step 9), writes them to a
    private env-file alongside the raw ``extra_env`` KEY=VALUE strings (step 11).
    The ``GOGA_SKIP_STAGES`` entry is layered in after the workflow env vars
    when ``skip`` is non-empty (joined comma-separated). This cell surfaces
    and emits the ``Pipeline running with workflow "NAME"`` log line to stdout
    ONLY when a workflow will actually be applied (step 10). This cell surfaces
    NO dashboard URL line — this is the only host-side stdout besides the docker
    output stream.

    Args:
        home_env: ``home.env`` from the machine-wide home config — the
            lowest-priority env layer (project config and CLI win on key
            conflict). Survives where unconflicted.
        extra_env: Additional raw KEY=VALUE strings appended verbatim (a
            SEPARATE channel appended last, winning on key conflict).
        pipeline_env: ``config.pipeline.env`` merged on top of git identity and
            home.env (highest-priority of the dict layers).
        proxy: Resolved HTTP/HTTPS proxy URL; populates the proxy env vars when
            non-None.
        workflow: optional workflow name from ``--workflow``.
        no_workflow: flag from ``--no-workflow``.
        name: pipeline name (the auto-match basename).
        skip: raw stage names from the repeatable ``-s/--skip`` CLI option.
            When non-empty, the env-file carries
            ``GOGA_SKIP_STAGES=<comma-joined>`` so the in-container
            ``run_pipeline`` routine applies ``apply_skip_stages`` over the
            resolved workflow. Omitted when empty.

    Returns:
        Path to the written private env-file.
    """
    git_env = _read_git_config()
    # home.env is the BASE layer — lowest priority. Git identity and project
    # (config.pipeline.env) override it; project wins over git (unchanged
    # precedence). CLI extra_env is a separate raw channel appended last by
    # _write_env_file, so it still wins on key conflict.
    env = {**home_env, **git_env, **pipeline_env}
    # AFM_DIR redirects afm state (flows, run-state) to the rw-mounted persistent
    # directory at /home/goga/pipeline; ~/.afm/config.yaml stays the config
    # source regardless (see the `afm` practice).
    env["AFM_DIR"] = _IN_CONTAINER_AFM_DIR
    if proxy is not None:
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["NO_PROXY"] = "localhost,127.0.0.1"
    # Step 9 — workflow env-file decision matrix (host-side, BEFORE launch). The
    # log name is set only when a workflow will actually be applied (step 10).
    workflow_env, workflow_log_name = _resolve_workflow_env(workflow, no_workflow, name)
    env.update(workflow_env)
    # GOGA_SKIP_STAGES carries the -s/--skip directives to the in-container
    # run_pipeline routine (step 6e applies apply_skip_stages over the resolved
    # workflow). Written ONLY when `skip` is non-empty; an empty tuple leaves
    # the env-file skip-free (discovery writes no env-file at all).
    if skip:
        env["GOGA_SKIP_STAGES"] = ",".join(skip)
    env_file = _write_env_file(env, extra_env)
    # Step 10 — the workflow log line. Emitted ONLY when a workflow will
    # actually be applied (explicit --workflow, or basename auto-match file
    # present on the host).
    if workflow_log_name is not None:
        click.echo(f'Pipeline running with workflow "{workflow_log_name}"')
    return env_file


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

    Run mode allocates a free port, writes a private afm-config tmpfile, ensures
    the persistent afm state host directory exists (wiping it first when
    ``clean`` is set), writes a private env-file layering ``home.env`` as the
    BASE layer under ``config.pipeline.env``, git identity, ``extra_env``,
    ``AFM_DIR``, the workflow env vars (per the workflow decision matrix), and —
    when ``proxy`` is set — the proxy env vars, emits the workflow log line when
    a workflow will actually be applied, optionally refreshes the image via
    ``docker_update`` (forwarding ``home.docker.build`` to image build in the
    build branch only), and runs the container via ``DockerRunner`` (forwarding
    ``home.docker.run`` as the separate ``extra_args`` keyword). The persistent
    directory is created before launch and never deleted in ``finally`` (it
    survives across runs and across the signal-exit path); only the tmpfile and
    env-file are unlinked.

    A SIGTERM/SIGINT handler is installed BEFORE writing the secret tmpfile/
    env-file (D7): a signal during the setup window — including the
    ``docker_update`` build — unwinds to the ``finally`` below and unlinks the
    secret files. The runner later installs its own handler that NESTS under this
    one (saving and restoring it).

    Args:
        name: Pipeline name without extension.
        config: Loaded project configuration.
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
        workflow: optional workflow name from ``--workflow``. Drives the
            workflow env-file decision matrix (step 9): when set, the env-file
            carries ``GOGA_WORKFLOW_NAME=<workflow>`` and the workflow log line
            names it. The file existence was already validated by the caller.
        no_workflow: flag from ``--no-workflow``. When True, the env-file
            carries ``GOGA_WORKFLOW_DISABLED=1`` and no workflow log line is
            emitted (mutually exclusive with ``workflow``, enforced by caller).
        skip: raw stage names from the repeatable ``-s/--skip`` CLI option.
            When non-empty, the env-file carries
            ``GOGA_SKIP_STAGES=<comma-joined>`` so the in-container
            ``run_pipeline`` routine applies ``apply_skip_stages`` over the
            resolved workflow. Omitted from the env-file when empty.
        parallel: optional int capping concurrently executing stages. When not
            None, appended to the in-container run argv as
            ``--parallel <parallel>`` (after ``--port``, before the container
            launch) so the in-container ``pipeline_cli`` forwards it to afm's
            ``--max-parallel``. When None (default), the flag is omitted — afm
            runs unbounded (backward compatible). Distinct from the Docker
            ``-p <port>:<port>`` port-publish token.

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

    def _on_signal(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    # D7 leak-prevention invariant: install BOTH the SIGTERM and SIGINT handlers
    # BEFORE writing the secret-bearing tmpfile/env-file, and write those files
    # inside the try below — so a signal (or any exception) raised in the window
    # that spans the tmpfile/env-file write, the docker_update build, and the
    # DockerRunner launch propagates through the finally, which unlinks the
    # secret files. Writing them before the handlers are installed would leak git
    # identity and pipeline secrets on disk if a signal arrived in that window.
    # The runner later installs its own handler that NESTS under these (saving
    # and restoring them), so the restores below return to the originals.
    prev_term = signal.signal(signal.SIGTERM, _on_signal)
    prev_int = signal.signal(signal.SIGINT, _on_signal)
    afm_config: Path | None = None
    env_file: Path | None = None
    try:
        wrapper_path = resolve_wrapper_path(config.pipeline.agent)
        afm_config = _write_afm_config_tmpfile(wrapper_path)
        env_file = _build_env_file(
            home_env=home.env,
            extra_env=extra_env,
            pipeline_env=config.pipeline.env,
            proxy=proxy,
            workflow=workflow,
            no_workflow=no_workflow,
            name=name,
            skip=skip,
        )

        project_dir = Path.cwd().resolve()
        # Nested mounts: project as /workspace (container working dir); the
        # persistent afm state host dir read-write at /home/goga/pipeline
        # (survives across runs); the afm-config tmpfile read-only at the FIXED
        # path /home/goga/.afm/config.yaml (independent of AFM_DIR). Then each
        # credential mount, read-only.
        mounts = [
            f"{project_dir}:/workspace",
            f"{runtime_dir}:{_IN_CONTAINER_AFM_DIR}",
            f"{afm_config}:/home/goga/.afm/config.yaml:ro",
        ]
        for host_path, container_path in resolve_credential_mounts():
            mounts.append(f"{host_path}:{container_path}:ro")

        # args = the post-image command (the in-container goga.pipeline run call +
        # its port); params = the docker-run options the runner translates to
        # flags via the shared param→flag rule.
        args = ["-m", "goga.pipeline", "run", name, "--port", str(port)]
        # --parallel <parallel> is appended to the in-container run argv ONLY when
        # not None (backward compatible — absent ⇒ no flag ⇒ afm unbounded). It is
        # appended after --port and before the container launch; the in-container
        # pipeline_cli forwards it to afm's --max-parallel. Distinct from the
        # Docker -p <port>:<port> port-publish token (params["p"] below).
        if parallel is not None:
            args += ["--parallel", str(parallel)]
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

        # First-run safety net: build the local image if it is absent and a
        # project Dockerfile is declared. No-op when the image exists or no
        # Dockerfile is set. Fatal build surfaces as ClickException (D5). Runs
        # inside the try so the D7 leak-prevention invariant covers this window:
        # the secret tmpfile/env-file are already written above, and a fatal
        # build unwinds to the finally below which unlinks them.
        # home.docker.build is forwarded to image build (build branch only).
        try:
            docker_build_if_not_exist(config.image, config.dockerfile, extra_args=home.docker.build)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

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

        # extra_args is a SEPARATE keyword to DockerRunner.run (NOT part of
        # params, which is unpacked via **). home.docker.run tokens are appended
        # verbatim AFTER the translated flags and BEFORE the image, never
        # translated to an --extra-args flag.
        return DockerRunner(config.image).run(args, extra_args=home.docker.run, **params)
    finally:
        # Only the tmpfile and env-file are deleted — the persistent afm state
        # directory (runtime_dir) survives under EVERY exit path.
        if afm_config is not None:
            afm_config.unlink(missing_ok=True)
        if env_file is not None:
            env_file.unlink(missing_ok=True)
        signal.signal(signal.SIGTERM, prev_term)
        signal.signal(signal.SIGINT, prev_int)


def run_pipeline_container(  # noqa: PLR0913, PLR0917
    name: str | None,
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

    Home (machine-wide) config from ``~/.goga/config.yml`` is loaded once up
    front (both modes) — an absent file yields an empty ``HomeConfig`` (no-op).
    ``home.env`` is the lowest-priority container env layer in RUN mode only
    (project ``pipeline.env`` and CLI win on key conflict); discovery writes no
    env-file, so ``home.env`` does not apply there. ``home.docker.run`` is
    forwarded to every ``DockerRunner.run`` as a separate ``extra_args`` keyword
    (both modes). ``home.docker.build`` is forwarded to image build
    (``docker_build_if_not_exist`` first-run safety net, ``docker_update``
    ``--update``) in the build branch only.

    Discovery mode (``name is None``) runs ``-m goga.pipeline list`` and ignores
    ``extra_env``, ``proxy``, ``clean``, ``workflow``, ``no_workflow``,
    ``skip``, and ``parallel`` — it honours only ``hosts`` (``--add-host`` flags)
    and ``update`` (conditional image pull); no env-file is written and no afm
    state directory is involved.

    Run mode (``name`` provided) allocates a free port, writes a private
    afm-config tmpfile (``client.command: <resolved wrapper path>`` — the
    absolute ``resolve_wrapper_path(config.pipeline.agent)`` value, never a bare
    agent name) mounted read-only at the FIXED path
    ``/home/goga/.afm/config.yaml``, ensures the persistent afm state host
    directory exists (wiping it first when ``clean`` is set), writes a private
    env-file layering ``home.env`` as the BASE layer under
    ``config.pipeline.env``, git identity, ``extra_env`` (raw KEY=VALUE strings),
    ``AFM_DIR=/home/goga/pipeline``, the workflow env vars (per the workflow
    decision matrix), the ``GOGA_SKIP_STAGES`` entry (when ``skip`` is
    non-empty), and — when ``proxy`` is set — the proxy env vars, mounts
    the persistent directory read-write at ``/home/goga/pipeline`` (it survives
    across runs and the signal-exit path), adds ``--add-host`` flags from
    ``hosts``, mounts every credential file from ``resolve_credential_mounts()``
    read-only, emits the workflow log line when a workflow will actually be
    applied, optionally refreshes the image via ``docker_update`` (forwarding
    ``home.docker.build`` to image build in the build branch only), and runs
    ``-m goga.pipeline run <name> --port <port>`` via ``DockerRunner`` (forwarding
    ``home.docker.run`` as ``extra_args``).

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
        update: When True, refresh the image before launch via ``docker_update``
            (build when a project Dockerfile is declared, else pull). When False
            (default), skip the refresh. Effective in both modes.
        workflow: optional workflow name forwarded from the ``--workflow`` CLI
            flag. In run mode, the env-file carries ``GOGA_WORKFLOW_NAME=<workflow>``
            and the workflow log line names it (file existence already validated
            by the caller). Ignored in discovery mode (``name is None``).
        no_workflow: flag forwarded from the ``--no-workflow`` CLI flag. In run
            mode, the env-file carries ``GOGA_WORKFLOW_DISABLED=1`` and no
            workflow log line is emitted; mutually exclusive with ``workflow``
            (enforced by the caller). Ignored in discovery mode.
        skip: raw stage names forwarded from the repeatable ``-s/--skip`` CLI
            option (default empty). In run mode, the env-file carries
            ``GOGA_SKIP_STAGES=<comma-joined>`` when non-empty so the
            in-container ``run_pipeline`` routine applies ``apply_skip_stages``
            over the resolved workflow; the host does NOT validate the names
            (validation is in-container). Omitted from the env-file when empty.
            Ignored in discovery mode.
        parallel: optional int (None when absent) capping concurrently executing
            stages, forwarded from the ``-p/--parallel`` CLI option. In run mode,
            appended to the in-container run argv as ``--parallel <parallel>``
            ONLY when not None (the in-container ``pipeline_cli`` forwards it to
            afm's ``--max-parallel``); omitted when None so afm runs unbounded
            (backward compatible). Not defaulted — None ⇒ unbounded. Ignored in
            discovery mode (no afm). Distinct from the Docker
            ``-p <port>:<port>`` port-publish token.

    Returns:
        The container's exit code.

    Raises:
        click.ClickException: When docker is missing, ``config.image`` is None,
            the home config file is malformed (a missing file is the normal
            no-op state), or a fatal image build is surfaced (D5).
        SystemExit: ``128 + signum`` when SIGTERM/SIGINT is received during run.
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

    if name is None:
        return _run_discovery(config, home, container_name, hosts, update)

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
