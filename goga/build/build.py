from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from ..agents import resolve_wrapper_path
from ..config import Config

logger = logging.getLogger(__name__)

DEFAULTS_PACKAGE_DIR = Path(__file__).parent.parent / "config" / "defaults"

_DEFAULT_CLAUDE_ARGS = "--dangerously-skip-permissions --output-format stream-json --verbose"


def _unquote_git_path(raw: str) -> str | None:
    if not raw.startswith('"'):
        return raw
    end = raw.find('"', 1)
    if end == -1:
        return None
    return raw[1:end].replace('\\"', '"').replace("\\\\", "\\")


def _parse_porcelain_path(line: str) -> str | None:
    if len(line) < len("XY "):
        return None
    raw = line[3:]
    if not raw:
        return None
    if " -> " in raw:
        new_path = raw.split(" -> ", 1)[1]
        return _unquote_git_path(new_path)
    if raw.startswith('"'):
        return _unquote_git_path(raw)
    return raw


def _find_uncommitted_manifests() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown error"
        logger.error("git status failed", extra={"detail": detail})
        raise RuntimeError(f"git status failed: {detail}")

    uncommitted: list[str] = []
    for line in result.stdout.splitlines():
        path = _parse_porcelain_path(line)
        if path and Path(path).name == "CODEMANIFEST":
            uncommitted.append(path)
    return uncommitted


def _write_ralphex_config(config: Config, wrapper_path: str) -> None:
    """Write the .ralphex/config INI for ralphex with the resolved wrapper path.

    Populates the ralphex config keys covered by the agent-wrappers contract:
    `claude_command` set to the resolved absolute wrapper path, `claude_args`
    set to its fixed default (no config field overrides it today),
    `codex_enabled` derived from `BuildConfig`, and `preserve_anthropic_api_key`
    pinned to `true` so the ralphex runner does not unset `ANTHROPIC_API_KEY`
    before invoking the agent wrapper. No codex-specific ralphex keys
    are written.

    Args:
        config: Project configuration with build settings.
        wrapper_path: Resolved absolute in-container wrapper path.
    """
    ralphex_dir = Path(".ralphex")
    ralphex_dir.mkdir(exist_ok=True)

    codex_enabled = str(config.build.codex_review or False).lower()

    config_lines = [
        f"claude_command = {wrapper_path}",
        f"claude_args = {_DEFAULT_CLAUDE_ARGS}",
        f"codex_enabled = {codex_enabled}",
        "preserve_anthropic_api_key = true",
    ]

    (ralphex_dir / "config").write_text("\n".join(config_lines) + "\n")
    logger.info("wrote .ralphex/config", extra={"claude_command": wrapper_path})


def _copy_defaults(config: Config) -> int:
    logger.info("copying defaults")

    defaults_dir = DEFAULTS_PACKAGE_DIR.resolve()

    if not defaults_dir.is_dir():
        logger.error("defaults directory not found", extra={"path": str(defaults_dir)})
        return 1

    ralphex_dir = Path(".ralphex")

    prompts_src = Path(config.build.prompts_dir) if config.build.prompts_dir else defaults_dir / "prompts"
    agents_src = Path(config.build.agents_dir) if config.build.agents_dir else defaults_dir / "agents"

    for src_dir, dest_name in ((prompts_src, "prompts"), (agents_src, "agents")):
        if not src_dir.is_dir():
            continue
        dest_dir = ralphex_dir / dest_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src_file in src_dir.iterdir():
            if not src_file.is_file():
                continue
            dest_file = dest_dir / src_file.name
            shutil.copy2(src_file, dest_file)

    return 0


def _assemble_command(plan: str, config: Config, cli_options: dict) -> list[str]:
    cmd = ["ralphex", plan, "--config-dir", ".ralphex/"]

    def resolve(flag_name: str, cli_key: str, config_key: str, is_flag: bool = False) -> None:
        cli_value = cli_options.get(cli_key)
        if is_flag:
            if cli_value or getattr(config.build, config_key):
                cmd.append(f"--{flag_name}")
        else:
            value = cli_value if cli_value is not None else getattr(config.build, config_key)
            if value is not None and value not in {"", 0}:
                cmd.extend([f"--{flag_name}", str(value)])

    resolve("worktree", "worktree", "worktree", is_flag=True)
    resolve("skip-finalize", "skip_finalize", "skip_finalize", is_flag=True)
    resolve("session-timeout", "session_timeout", "session_timeout")
    resolve("idle-timeout", "idle_timeout", "idle_timeout")
    resolve("wait", "wait", "wait")
    resolve("max-iterations", "max_iterations", "max_iterations")
    resolve("review-patience", "review_patience", "review_patience")

    return cmd


def build(plan: str, config: Config, cli_options: dict) -> int:
    """Execute the build pipeline for a given plan.

    Validates uncommitted CODEMANIFEST files, resolves the agent wrapper path,
    writes the ralphex config, copies default prompts and agents, and launches
    the ralphex build command.

    Args:
        plan: Path to the build plan file.
        config: Project configuration with build settings and task executor.
        cli_options: CLI flags such as dry_run, skip_manifest_check, worktree, etc.

    Returns:
        0 on success, 1 on failure.
    """
    if not cli_options.get("skip_manifest_check"):
        try:
            uncommitted = _find_uncommitted_manifests()
        except RuntimeError:
            return 1
        if uncommitted:
            logger.error("uncommitted codemanifest files found", extra={"paths": uncommitted})
            return 1

    wrapper_path = resolve_wrapper_path(config.build.task_executor.agent)

    _write_ralphex_config(config, wrapper_path)

    copy_result = _copy_defaults(config)
    if copy_result != 0:
        return copy_result

    cmd = _assemble_command(plan, config, cli_options)
    cmd_str = shlex.join(cmd)

    if cli_options.get("dry_run"):
        logger.info("dry run", extra={"command": cmd_str})
        return 0

    if not shutil.which("ralphex"):
        logger.error("ralphex not found in path")
        return 1

    logger.info("running build", extra={"command": cmd_str})
    return subprocess.call(cmd, env={**os.environ, **config.build.task_executor.env})
