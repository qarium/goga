from __future__ import annotations

import json
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from ..config import Config

CLAUDE_WRAPPER_SCRIPT = '#!/bin/bash\nexec env ANTHROPIC_API_KEY="$ANTHROPIC_API_TOKEN" claude "$@"\n'
CODEX_WRAPPER_SCRIPT = '#!/bin/bash\nexec codex "$@" -m "$CODEX_MODEL"\n'

DEFAULTS_PACKAGE_DIR = Path(__file__).parent.parent / "config" / "defaults"

RALPHEX_CONFIG_DEFAULTS = {
    "claude_command": ".ralphex/claude-wrapper.sh",
    "claude_args": "--dangerously-skip-permissions --output-format stream-json --verbose",
}


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
        print(f"git status failed: {detail}", file=sys.stderr)
        raise RuntimeError(f"git status failed: {detail}")
    uncommitted: list[str] = []
    for line in result.stdout.splitlines():
        path = _parse_porcelain_path(line)
        if path and Path(path).name == "CODEMANIFEST":
            uncommitted.append(path)
    return uncommitted


def _cleanup_ralphex_dir() -> None:
    ralphex_dir = Path(".ralphex")
    if ralphex_dir.is_dir():
        shutil.rmtree(ralphex_dir)
        print("Removed .ralphex/", file=sys.stderr)


def _run_precondition(config: Config) -> int:
    agent = config.build.task_executor.agent
    if agent not in ("claude", "codex"):
        print(f"Unsupported agent: {agent}", file=sys.stderr)
        return 1
    if agent == "claude":
        try:
            _precondition_claude(config)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if agent == "codex":
        _precondition_codex()
    return 0


def _precondition_claude(config: Config) -> None:
    _create_claude_settings(config)
    _create_claude_wrapper(config)


def _create_claude_settings(config: Config) -> None:
    print("Creating .claude/settings.json...", file=sys.stderr)

    claude_dir = Path(".claude")
    claude_dir.mkdir(exist_ok=True)

    settings_path = claude_dir / "settings.json"
    settings: dict = {}
    if settings_path.is_file():
        try:
            with settings_path.open() as f:
                settings = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON in .claude/settings.json: {exc}", file=sys.stderr)
            raise RuntimeError(f"Invalid JSON in .claude/settings.json: {exc}") from exc

    settings.setdefault("env", {})
    for key, value in config.build.task_executor.env.items():
        settings["env"][key] = value

    settings["attribution"] = {"commit": "", "pr": ""}

    with settings_path.open("w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def _precondition_codex() -> None:
    _create_codex_wrapper()


def _create_codex_wrapper() -> None:
    print("Creating .ralphex/config for codex...", file=sys.stderr)

    ralphex_dir = Path(".ralphex")
    ralphex_dir.mkdir(exist_ok=True)

    wrapper_path = ralphex_dir / "codex-wrapper.sh"
    wrapper_path.write_text(CODEX_WRAPPER_SCRIPT)
    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (ralphex_dir / "config").write_text(
        "executor = codex\n"
        "codex_command = .ralphex/codex-wrapper.sh\n"
        "codex_sandbox = danger-full-access\n"
        "codex_reasoning_effort = high\n"
    )


def _create_claude_wrapper(config: Config) -> None:
    print("Creating .ralphex/claude-wrapper.sh...", file=sys.stderr)

    ralphex_dir = Path(".ralphex")
    ralphex_dir.mkdir(exist_ok=True)

    wrapper_path = ralphex_dir / "claude-wrapper.sh"
    wrapper_path.write_text(CLAUDE_WRAPPER_SCRIPT)

    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    config_path = ralphex_dir / "config"
    config_lines: list[str] = []
    if config_path.is_file():
        config_lines = config_path.read_text().splitlines()

    codex_value = str(config.build.codex_review or False).lower()
    codex_line = f"codex_enabled = {codex_value}"

    existing_keys: set[str] = set()
    codex_found = False
    for i, line in enumerate(config_lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            existing_keys.add(key)
            if key == "codex_enabled":
                config_lines[i] = codex_line
                codex_found = True

    for key, value in RALPHEX_CONFIG_DEFAULTS.items():
        if key not in existing_keys:
            config_lines.append(f"{key} = {value}")

    if not codex_found:
        config_lines.append(codex_line)

    config_path.write_text("\n".join(config_lines) + "\n")


def _copy_defaults(config: Config) -> int:
    print("Copying defaults...", file=sys.stderr)

    defaults_dir = DEFAULTS_PACKAGE_DIR.resolve()

    if not defaults_dir.is_dir():
        print(f"Error: defaults directory not found: {defaults_dir}", file=sys.stderr)
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

    Validates uncommitted CODEMANIFEST files, runs agent-specific preconditions,
    copies default prompts and agents, and launches the ralphex build command.

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
            print("Error: Uncommitted CODEMANIFEST files found:", file=sys.stderr)
            for path in uncommitted:
                print(f"  {path}", file=sys.stderr)
            return 1

    _cleanup_ralphex_dir()

    for step in (_run_precondition, _copy_defaults):
        result = step(config)
        if result != 0:
            return result

    cmd = _assemble_command(plan, config, cli_options)
    cmd_str = shlex.join(cmd)

    if cli_options.get("dry_run"):
        print(f"Dry run: {cmd_str}", file=sys.stderr)
        return 0

    if not shutil.which("ralphex"):
        print("Error: ralphex not found in PATH", file=sys.stderr)
        return 1

    print(f"Running: {cmd_str}", file=sys.stderr)
    return subprocess.call(cmd)
