from __future__ import annotations

import shutil
from pathlib import Path

import click

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


def _get_dsl_source() -> Path:
    """Return the path to the DSL spec file."""
    return Path(__file__).parent.parent / ".usages" / "dsl.md"


def _install_skills(source: Path, target: Path, dsl_source: Path) -> list[str]:
    """Install skill directories from source to target. Returns list of skill names."""
    target_skills = target / "skills"
    target_skills.mkdir(exist_ok=True)
    installed = []
    for entry in (source / "skills").iterdir():
        if entry.is_dir():
            dest = target_skills / entry.name
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(entry, dest)
            if dsl_source.is_file():
                shutil.copy2(dsl_source, dest / "dsl.md")
            installed.append(entry.name)
    return sorted(installed)


def _print_summary(commands: list[str], skills: list[str], target: Path) -> None:
    """Print installation summary to stdout."""
    click.echo(f"Installed goga commands to {target}/commands/goga/")
    click.echo(f"Installed {len(commands)} commands: {', '.join(commands)}")
    click.echo(f"Installed goga skills to {target}/skills/")
    click.echo(f"Installed {len(skills)} skills: {', '.join(skills)}")


@click.command()
@click.option("--agent", default="claude", help="Target AI agent")
@click.pass_context
def init(ctx: click.Context, agent: str) -> None:
    """Install goga skills and commands into the target AI agent configuration."""
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
        commands = _install_commands(source, target)
        skills = _install_skills(source, target, _get_dsl_source())
        _print_summary(commands, skills, target)
    except OSError as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)

    ctx.exit(0)
