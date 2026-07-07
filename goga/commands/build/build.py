from __future__ import annotations

import logging
import os
import signal
import stat
import subprocess
import tempfile
from pathlib import Path

import click
import yaml

from ...agents import resolve_credential_mounts
from ...config import load_config

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


def _pull_image(image: str) -> None:
    """Pull the build image to refresh an already-present local image before launch.

    Args:
        image: Docker image reference to pull.

    Note:
        A non-zero exit code from ``docker pull`` is not fatal: the failure is
        logged as a warning and the build proceeds with the locally available image.
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
    extra_env: tuple[str, ...],
) -> Path:
    """Write environment variables to a private temporary env file.

    The file is created with mode 0600 so only the owner can read it.

    Args:
        env: Mapping of environment variables to write as KEY=VALUE lines.
        extra_env: Additional raw KEY=VALUE strings to append verbatim.

    Returns:
        Path to the written temporary file.
    """
    fd, path = tempfile.mkstemp(prefix="goga-env-")

    with os.fdopen(fd, "w") as f:
        Path(path).chmod(stat.S_IRUSR | stat.S_IWUSR)

        for k, v in env.items():
            f.write(f"{k}={v}\n")
        for pair in extra_env:
            f.write(f"{pair}\n")

    return Path(path)


def _cli_flags_to_args(cli_flags: dict[str, bool | str | int | None]) -> list[str]:
    """Render the build cli_flags map into trailing goga.build argument list.

    Args:
        cli_flags: Build flags forwarded to the in-container entrypoint.

    Returns:
        A flat list of CLI argument tokens (e.g. ``["--worktree", "--wait", "5m"]``).
    """
    args: list[str] = []
    if cli_flags.get("dry_run"):
        args.append("--dry-run")
    if cli_flags.get("worktree"):
        args.append("--worktree")
    if cli_flags.get("skip_finalize"):
        args.append("--skip-finalize")
    if cli_flags.get("skip_manifest_check"):
        args.append("--skip-manifest-check")

    for flag in ("session_timeout", "idle_timeout", "wait", "max_iterations", "review_patience"):
        val = cli_flags.get(flag)
        if val is not None:
            args.extend([f"--{flag.replace('_', '-')}", str(val)])

    return args


def _build_docker_cmd(  # noqa: PLR0913
    plan: str,
    image: str,
    env_file: Path,
    cli_flags: dict[str, bool | str | int | None],
    container_name: str,
    merged_hosts: dict[str, str] | None = None,
) -> list[str]:
    """Assemble the docker run command that launches goga.build inside a container.

    Args:
        plan: Plan identifier passed to `goga.build` as the positional argument.
        image: Docker image to run.
        env_file: Path to the env file mounted via `--env-file`.
        cli_flags: Build flags forwarded to the in-container entrypoint.
        container_name: Name assigned to the container via `--name`.
        merged_hosts: Resolved host→IP mapping (config.build.hosts merged with
            parsed ``--add-host`` CLI entries). Each pair becomes a
            ``--add-host HOST:IP`` flag. ``None`` adds no host entries.

    Returns:
        The full docker command as a list of string arguments.
    """
    if merged_hosts is None:
        merged_hosts = {}

    project_dir = Path.cwd().resolve()

    cmd: list[str] = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--entrypoint",
        "python3",
        "-v",
        f"{project_dir}:/workspace",
        "-w",
        "/workspace",
    ]

    for host, ip in merged_hosts.items():
        cmd.extend(["--add-host", f"{host}:{ip}"])

    cmd.extend(["--env-file", str(env_file)])

    for host_path, container_path in resolve_credential_mounts():
        cmd.extend(["-v", f"{host_path}:{container_path}:ro"])

    cmd.append(image)

    cmd.extend(["-m", "goga.build", plan])
    cmd.extend(_cli_flags_to_args(cli_flags))

    return cmd


@click.command()
@click.argument("plan")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
@click.option("--worktree", is_flag=True, help="Enable ralphex worktree mode")
@click.option("--skip-finalize", is_flag=True, help="Skip finalization")
@click.option("--skip-manifest-check", is_flag=True, help="Skip CODEMANIFEST uncommitted check")
@click.option("--session-timeout", type=str, default=None, help="Session timeout")
@click.option("--idle-timeout", type=str, default=None, help="Idle timeout")
@click.option("--wait", type=str, default=None, help="Wait time")
@click.option("--max-iterations", type=int, default=None, help="Max iterations")
@click.option("--review-patience", type=int, default=None, help="Review patience")
@click.option("-e", "--env", "extra_env", multiple=True, help="Pass env var to container (KEY=VALUE)")
@click.option("--proxy", type=str, default=None, help="HTTP/HTTPS proxy URL; overrides config.build.proxy")
@click.option(
    "--add-host",
    "add_host",
    multiple=True,
    help="Add a docker run --add-host HOST:IP entry; merges on top of config.build.hosts",
)
@click.option(
    "--update",
    "-u",
    "update",
    is_flag=True,
    default=False,
    help="Pull the image before launching the container",
)
@click.pass_context
def build(  # noqa: PLR0913
    ctx: click.Context,
    plan: str,
    dry_run: bool,
    worktree: bool,
    skip_finalize: bool,
    skip_manifest_check: bool,
    session_timeout: str | None,
    idle_timeout: str | None,
    wait: str | None,
    max_iterations: int | None,
    review_patience: int | None,
    extra_env: tuple[str, ...],
    proxy: str | None,
    add_host: tuple[str, ...],
    update: bool,
) -> None:
    """Build code via ralphex by launching goga.build inside a Docker container.

    Args:
        ctx: Click execution context used to control process exit codes.
        plan: Plan identifier forwarded to the in-container `goga.build` module.
        dry_run: When True, assemble the command but do not execute it.
        worktree: Enable ralphex worktree mode inside the container.
        skip_finalize: Skip the ralphex finalization step.
        skip_manifest_check: Skip the CODEMANIFEST uncommitted-files check.
        session_timeout: Optional session timeout forwarded to the build.
        idle_timeout: Optional idle timeout forwarded to the build.
        wait: Optional wait time forwarded to the build.
        max_iterations: Optional iteration cap forwarded to the build.
        review_patience: Optional review patience forwarded to the build.
        extra_env: Additional KEY=VALUE environment variables for the container.
        proxy: Optional HTTP/HTTPS proxy URL from ``--proxy``. When None, falls
            back to ``config.build.proxy``. The resolved value (CLI wins over
            config) drives HTTP_PROXY/HTTPS_PROXY/NO_PROXY in the env-file.
        add_host: Raw ``HOST:IP`` strings from the repeatable ``--add-host``
            option. Merged on top of ``config.build.hosts``; CLI wins on key
            conflict. Each entry becomes a docker run ``--add-host`` flag.
        update: When True, pull the image before launch. When False (default),
            skip the pull and use the locally available image.

    Raises:
        click.ClickException: When docker is missing, configuration cannot be
            loaded, or the build image is not configured.
    """
    if not _check_docker():
        raise click.ClickException("docker not found in PATH")

    try:
        config = load_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    cli_flags = {
        "worktree": worktree,
        "skip_finalize": skip_finalize,
        "skip_manifest_check": skip_manifest_check,
        "session_timeout": session_timeout,
        "idle_timeout": idle_timeout,
        "wait": wait,
        "max_iterations": max_iterations,
        "review_patience": review_patience,
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

    # Reject the missing-image case before creating any temp files: the env file
    # (written below) carries git identity and task_executor secrets and is only
    # unlinked by the finally of the try block below, so creating it here and then
    # raising would leak it on disk.
    if config.image is None:
        raise click.ClickException("image in .goga/config.yml is not set")

    git_env = _read_git_config()
    env = {**git_env, **config.build.task_executor.env}

    # When a proxy is resolved (CLI or config), populate the standard proxy env
    # vars. NO_PROXY is fixed at localhost,127.0.0.1 — there is no --no-proxy.
    if resolved_proxy is not None:
        env["HTTP_PROXY"] = resolved_proxy
        env["HTTPS_PROXY"] = resolved_proxy
        env["NO_PROXY"] = "localhost,127.0.0.1"

    env_file = _write_env_file(env, extra_env)

    container_name = f"goga-build-{os.getpid()}"

    def _on_sigterm(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    _prev_sigterm = signal.signal(signal.SIGTERM, _on_sigterm)

    try:
        docker_cmd = _build_docker_cmd(
            plan=plan,
            image=config.image,
            env_file=env_file,
            cli_flags=cli_flags,
            container_name=container_name,
            merged_hosts=merged_hosts,
        )

        if dry_run:
            ctx.exit(0)

        if update:
            _pull_image(config.image)

        docker_proc = subprocess.Popen(docker_cmd)

        ctx.exit(docker_proc.wait())
    finally:
        env_file.unlink(missing_ok=True)
        subprocess.run(
            ["docker", "kill", container_name],
            check=False,
            capture_output=True,
        )
        signal.signal(signal.SIGTERM, _prev_sigterm)
