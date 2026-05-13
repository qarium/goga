from __future__ import annotations

import shutil
from pathlib import Path

import click
import yaml

from goga.config import load_config

AGENT_DIRS: dict[str, str] = {"claude": ".claude"}


def _resolve_target_dir(agent: str) -> Path:
    """Map agent name to target directory path."""
    if agent not in AGENT_DIRS:
        raise ValueError(f"Unsupported agent: {agent}")
    return Path.home() / AGENT_DIRS[agent]


def _get_source_dir() -> Path:
    """Return the path to the goga agent resources directory."""
    return Path(__file__).parent.parent / "agent"


def _install_commands(source: Path, target: Path) -> list[str]:
    """Install command files from source to target. Returns list of command names."""
    target_commands = target / "commands" / "goga"
    shutil.rmtree(target_commands, ignore_errors=True)
    shutil.copytree(source / "commands", target_commands)
    return sorted(p.stem for p in target_commands.glob("*.md"))


def _install_skills(source: Path, target: Path) -> list[str]:
    """Install skill directories from source to target. Returns list of skill names."""
    target_skills = target / "skills"
    target_skills.mkdir(exist_ok=True)
    installed = []
    for entry in (source / "skills").iterdir():
        if entry.is_dir():
            dest = target_skills / entry.name
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(entry, dest)
            installed.append(entry.name)
    return sorted(installed)


def _cleanup_goga_skills(target: Path) -> int:
    """Remove all goga-* skill directories from target/skills/. Returns count removed."""
    target_skills = target / "skills"
    if not target_skills.is_dir():
        return 0
    removed = 0
    for entry in target_skills.iterdir():
        if entry.is_dir() and entry.name.startswith("goga-"):
            shutil.rmtree(entry)
            removed += 1
    return removed


def _print_summary(commands: list[str], skills: list[str], target: Path) -> None:
    """Print installation summary to stdout."""
    click.echo(f"Installed goga commands to {target}/commands/goga/")
    click.echo(f"Installed {len(commands)} commands: {', '.join(commands)}")
    click.echo(f"Installed goga skills to {target}/skills/")
    click.echo(f"Installed {len(skills)} skills: {', '.join(skills)}")


@click.command()
@click.option("--agent", default=None, help="Target AI agent")
@click.pass_context
def install(ctx: click.Context, agent: str | None) -> None:
    """Install goga skills and commands into the target AI agent configuration."""
    try:
        config = load_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    agent = agent if agent is not None else config.build.task_executor.agent

    try:
        target = _resolve_target_dir(agent)
    except ValueError:
        click.echo(f"Error: unsupported agent '{agent}'", err=True)
        ctx.exit(1)

    source = _get_source_dir()
    if not source.is_dir():
        click.echo(f"Error: agent resources not found at {source}", err=True)
        ctx.exit(1)

    target.mkdir(parents=True, exist_ok=True)

    try:
        _cleanup_goga_skills(target)
        commands = _install_commands(source, target)
        skills = _install_skills(source, target)
        _print_summary(commands, skills, target)
    except OSError as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)

    ctx.exit(0)
