from __future__ import annotations

import os
import signal
import stat
import subprocess
import tempfile
from pathlib import Path

import click
import yaml

from ...config import load_config


def _check_docker() -> bool:
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
    try:
        name_result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, check=False,
        )
        email_result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, check=False,
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
    fd, path = tempfile.mkstemp(prefix="goga-env-")
    with os.fdopen(fd, "w") as f:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        for k, v in env.items():
            f.write(f"{k}={v}\n")
        for pair in extra_env:
            f.write(f"{pair}\n")
    return Path(path)


def _build_docker_cmd(
    plan: str,
    image: str,
    env_file: Path,
    cli_flags: dict[str, bool | str | int | None],
    container_name: str,
) -> list[str]:
    project_dir = Path.cwd().resolve()

    cmd: list[str] = ["docker", "run", "--rm", "--name", container_name,
                      "--entrypoint", "python3", "-v",
                      f"{project_dir}:/workspace", "-w",
                      "/workspace", "--env-file", str(env_file), image]

    cmd.extend(["-m", "goga.build", plan])

    if cli_flags.get("dry_run"):
        cmd.append("--dry-run")
    if cli_flags.get("worktree"):
        cmd.append("--worktree")
    if cli_flags.get("skip_finalize"):
        cmd.append("--skip-finalize")
    if cli_flags.get("skip_manifest_check"):
        cmd.append("--skip-manifest-check")
    for flag in ("session_timeout", "idle_timeout", "wait"):
        val = cli_flags.get(flag)
        if val is not None:
            cmd.extend([f"--{flag.replace('_', '-')}", str(val)])
    for flag in ("max_iterations", "review_patience"):
        val = cli_flags.get(flag)
        if val is not None:
            cmd.extend([f"--{flag.replace('_', '-')}", str(val)])

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
) -> None:
    """Build code via ralphex. Launches goga.build inside a Docker container."""
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

    git_env = _read_git_config()
    env = {**git_env, **config.build.task_executor.env}
    env_file = _write_env_file(env, extra_env)

    if config.build.image is None:
        raise click.ClickException("image in .goga/config.yml is not set")

    container_name = f"goga-build-{os.getpid()}"

    def _on_sigterm(signum: int, frame: object) -> None:
        raise SystemExit(128 + signum)

    _prev_sigterm = signal.signal(signal.SIGTERM, _on_sigterm)

    try:
        docker_cmd = _build_docker_cmd(
            plan=plan,
            image=config.build.image,
            env_file=env_file,
            cli_flags=cli_flags,
            container_name=container_name,
        )

        if dry_run:
            ctx.exit(0)

        docker_proc = subprocess.Popen(docker_cmd)
        ctx.exit(docker_proc.wait())
    finally:
        env_file.unlink(missing_ok=True)
        subprocess.run(
            ["docker", "kill", container_name],
            check=False, capture_output=True,
        )
        signal.signal(signal.SIGTERM, _prev_sigterm)

