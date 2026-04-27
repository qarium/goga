from __future__ import annotations

import copy
import json
import shutil
import stat
import subprocess
from pathlib import Path

import click
import yaml

DEFAULT_BUILD_CONFIG: dict = {
    "worktree": False,
    "skip_finalize": False,
    "codex_enabled": False,
    "session_timeout": "",
    "idle_timeout": "",
    "wait": "",
    "max_iterations": 0,
    "review_patience": 0,
    "prompts_dir": "",
    "agents_dir": "",
    "models": {
        "haiku": "glm-4.7",
        "sonnet": "glm-5-turbo",
        "opus": "glm-5.1",
        "base_url": "https://api.z.ai/api/anthropic",
    },
}

CLAUDE_WRAPPER_SCRIPT = '#!/bin/bash\nexec env ANTHROPIC_API_KEY="$ANTHROPIC_API_TOKEN" claude "$@"\n'

DEFAULTS_PACKAGE_DIR = Path(__file__).parent.parent / "config" / "defaults"


def _unquote_git_path(raw: str) -> str | None:
    """Unquote a git C-style quoted path."""
    if not raw.startswith('"'):
        return raw
    end = raw.find('"', 1)
    if end == -1:
        return None
    return raw[1:end].replace('\\"', '"').replace("\\\\", "\\")


def _parse_porcelain_path(line: str) -> str | None:
    """Extract file path from a git status --porcelain line.

    Handles quoted paths (spaces, special chars) and rename entries (old -> new).
    """
    # git porcelain format: XY<space>path (minimum 4 chars)
    if len(line) < len("XY "):
        return None
    raw = line[3:]  # skip two-char status (XY) + space
    if not raw:
        return None
    # Rename entry: old_path -> new_path
    if " -> " in raw:
        new_path = raw.split(" -> ", 1)[1]
        return _unquote_git_path(new_path)
    # Quoted path: "path with spaces"
    if raw.startswith('"'):
        return _unquote_git_path(raw)
    return raw


def _find_uncommitted_manifests() -> list[str]:
    """Find uncommitted CODEMANIFEST files via git status --porcelain."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown error"
        raise click.ClickException(f"git status failed: {detail}")
    uncommitted: list[str] = []
    for line in result.stdout.splitlines():
        path = _parse_porcelain_path(line)
        if path and Path(path).name == "CODEMANIFEST":
            uncommitted.append(path)
    return uncommitted


def _read_goga_yml() -> dict:  # noqa: C901
    """Read goga.yml from the project root, return the build section merged with defaults."""
    config = copy.deepcopy(DEFAULT_BUILD_CONFIG)
    goga_yml_path = Path("goga.yml")
    if not goga_yml_path.is_file():
        click.echo("goga.yml not found, using defaults")
        return config

    click.echo("Reading goga.yml...")
    with goga_yml_path.open() as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError:
            raise click.ClickException(f"Failed to parse {goga_yml_path}: invalid YAML") from None

    if not isinstance(data, dict) or "build" not in data:
        click.echo("No 'build' section in goga.yml, using defaults")
        return config

    build_section = data["build"]
    if not isinstance(build_section, dict):
        click.echo("Invalid 'build' section in goga.yml, using defaults")
        return config

    for key in config:
        if key == "models":
            continue
        if key in build_section:
            config[key] = build_section[key]

    if "models" in build_section and isinstance(build_section["models"], dict):
        for model_key in ("haiku", "sonnet", "opus", "base_url"):
            if model_key in build_section["models"]:
                config["models"][model_key] = build_section["models"][model_key]

    return config


def _create_claude_settings(config: dict) -> None:
    """Create or update .claude/settings.json with model overrides."""
    click.echo("Creating .claude/settings.json...")

    claude_dir = Path(".claude")
    claude_dir.mkdir(exist_ok=True)

    settings_path = claude_dir / "settings.json"
    settings: dict = {}
    if settings_path.is_file():
        with settings_path.open() as f:
            settings = json.load(f)

    models = config.get("models", DEFAULT_BUILD_CONFIG["models"])

    settings.setdefault("env", {})
    settings["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = models.get("haiku", DEFAULT_BUILD_CONFIG["models"]["haiku"])
    settings["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] = models.get("sonnet", DEFAULT_BUILD_CONFIG["models"]["sonnet"])
    settings["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] = models.get("opus", DEFAULT_BUILD_CONFIG["models"]["opus"])
    settings["env"]["ANTHROPIC_BASE_URL"] = models.get("base_url", DEFAULT_BUILD_CONFIG["models"]["base_url"])

    settings["attribution"] = {"commit": "", "pr": ""}

    with settings_path.open("w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


RALPHEX_CONFIG_DEFAULTS = {
    "claude_command": ".ralphex/claude-wrapper.sh",
    "claude_args": "--dangerously-skip-permissions --output-format stream-json --verbose",
}


def _create_claude_wrapper(config: dict) -> None:
    """Create .ralphex/claude-wrapper.sh and set ralphex config defaults. Overwrites on every run."""
    click.echo("Creating .ralphex/claude-wrapper.sh...")

    ralphex_dir = Path(".ralphex")
    ralphex_dir.mkdir(exist_ok=True)

    wrapper_path = ralphex_dir / "claude-wrapper.sh"
    wrapper_path.write_text(CLAUDE_WRAPPER_SCRIPT)

    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    config_path = ralphex_dir / "config"
    config_lines: list[str] = []
    if config_path.is_file():
        config_lines = config_path.read_text().splitlines()

    codex_value = str(config["codex_enabled"]).lower()
    codex_line = f"codex_enabled = {codex_value}"

    existing_keys: set[str] = set()
    codex_found = False
    for i, line in enumerate(config_lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and " = " in stripped:
            key = stripped.split(" = ", 1)[0].strip()
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


def _copy_defaults(config: dict) -> None:
    """Copy default prompts and agents from goga package to .ralphex/. Overwrites existing files."""
    click.echo("Copying defaults...")

    defaults_dir = DEFAULTS_PACKAGE_DIR.resolve()

    if not defaults_dir.is_dir():
        raise click.ClickException(f"defaults directory not found: {defaults_dir}")

    ralphex_dir = Path(".ralphex")

    prompts_src = Path(config["prompts_dir"]) if config.get("prompts_dir") else defaults_dir / "prompts"
    agents_src = Path(config["agents_dir"]) if config.get("agents_dir") else defaults_dir / "agents"

    for src_dir, dest_name in ((prompts_src, "prompts"), (agents_src, "agents")):
        if not src_dir.is_dir():
            continue
        dest_dir = ralphex_dir / dest_name
        dest_dir.mkdir(exist_ok=True)
        for src_file in src_dir.iterdir():
            if not src_file.is_file():
                continue
            dest_file = dest_dir / src_file.name
            shutil.copy2(src_file, dest_file)


def _assemble_command(plan: str, config: dict, cli_options: dict) -> list[str]:
    """Assemble the ralphex command with flags. Priority: CLI > goga.yml > defaults."""
    cmd = ["ralphex", plan, "--config-dir", ".ralphex/"]

    def resolve(flag_name: str, cli_key: str, config_key: str, is_flag: bool = False) -> None:
        cli_value = cli_options.get(cli_key)
        if is_flag:
            if cli_value or config.get(config_key):
                cmd.append(f"--{flag_name}")
        else:
            value = cli_value if cli_value is not None else config.get(config_key)
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
) -> None:
    """Build code via ralphex. Prepares environment and launches ralphex."""
    if not skip_manifest_check:
        uncommitted = _find_uncommitted_manifests()
        if uncommitted:
            click.echo("Error: Uncommitted CODEMANIFEST files found:", err=True)
            for path in uncommitted:
                click.echo(f"  {path}", err=True)
            ctx.exit(1)

    config = _read_goga_yml()
    _create_claude_settings(config)
    _create_claude_wrapper(config)
    _copy_defaults(config)

    cli_options = {
        "worktree": worktree,
        "skip_finalize": skip_finalize,
        "session_timeout": session_timeout,
        "idle_timeout": idle_timeout,
        "wait": wait,
        "max_iterations": max_iterations,
        "review_patience": review_patience,
    }

    cmd = _assemble_command(plan, config, cli_options)
    cmd_str = " ".join(cmd)

    if dry_run:
        click.echo(f"Dry run: {cmd_str}")
        ctx.exit(0)

    if not shutil.which("ralphex"):
        click.echo("Error: ralphex not found in PATH", err=True)
        ctx.exit(1)

    click.echo(f"Running: {cmd_str}")
    return_code = subprocess.call(cmd)
    ctx.exit(return_code)
