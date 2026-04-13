from __future__ import annotations

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

CLAUDE_WRAPPER_SCRIPT = '#!/bin/bash\nexec env ANTHROPIC_API_KEY="$ZAI_TOKEN" claude "$@"\n'

DEFAULTS_PACKAGE_DIR = Path(__file__).parent.parent / "config" / "defaults"


def _read_goga_yml() -> dict:
    """Read goga.yml from the project root, return the build section merged with defaults."""
    config = dict(DEFAULT_BUILD_CONFIG)
    goga_yml_path = Path("goga.yml")
    if not goga_yml_path.is_file():
        click.echo("goga.yml not found, using defaults")
        return config

    click.echo("Reading goga.yml...")
    with goga_yml_path.open() as f:
        data = yaml.safe_load(f)

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
    "codex_enabled": "false",
}


def _create_claude_wrapper() -> None:
    """Create .ralphex/claude-wrapper.sh with execute permission and set ralphex config defaults. Overwrites on every run."""
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

    existing_keys = set()
    for line in config_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and " = " in stripped:
            key = stripped.split(" = ", 1)[0].strip()
            existing_keys.add(key)

    for key, value in RALPHEX_CONFIG_DEFAULTS.items():
        if key not in existing_keys:
            config_lines.append(f"{key} = {value}")

    config_path.write_text("\n".join(config_lines) + "\n")


def _copy_defaults(config: dict) -> None:
    """Copy default prompts and agents from goga package to .ralphex/. Does NOT overwrite existing files."""
    click.echo("Copying defaults...")

    defaults_dir = DEFAULTS_PACKAGE_DIR.resolve()
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
            if not dest_file.exists():
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
@click.argument("plan", default="docs/plans/plan.md")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
@click.option("--worktree", is_flag=True, help="Enable ralphex worktree mode")
@click.option("--skip-finalize", is_flag=True, help="Skip finalization")
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
    session_timeout: str | None,
    idle_timeout: str | None,
    wait: str | None,
    max_iterations: int | None,
    review_patience: int | None,
) -> None:
    """Build code via ralphex. Prepares environment and launches ralphex."""
    config = _read_goga_yml()
    _create_claude_settings(config)
    _create_claude_wrapper()
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
