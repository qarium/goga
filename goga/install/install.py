from __future__ import annotations

import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

from goga.config import Config

AGENT_DIRS: dict[str, str] = {"claude": ".claude"}

DSL_SPEC_URL = "https://raw.githubusercontent.com/qarium/codemanifest/refs/heads/0.0.x/specs/ru.md"


def _resolve_target_dir(agent: str) -> Path:
    if agent not in AGENT_DIRS:
        raise ValueError(f"Unsupported agent: {agent}")
    return Path.home() / AGENT_DIRS[agent]


def _get_source_dir() -> Path:
    return Path(__file__).parent.parent / "agent"


def _install_commands(source: Path, target: Path) -> list[str]:
    target_commands = target / "commands" / "goga"
    shutil.rmtree(target_commands, ignore_errors=True)
    shutil.copytree(source / "commands", target_commands)
    return sorted(p.stem for p in target_commands.glob("*.md"))


def _install_skills(source: Path, target: Path) -> list[str]:
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


def _download_dsl_spec(target: Path) -> None:
    dsl_path = target / "skills" / "goga-cell" / "dsl.md"
    try:
        with urllib.request.urlopen(DSL_SPEC_URL, timeout=30) as response:
            data = response.read()
    except urllib.error.HTTPError as e:
        raise OSError(f"Failed to download DSL spec: HTTP {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise OSError(f"Failed to download DSL spec: {e.reason}") from e
    dsl_path.write_bytes(data)


def _cleanup_goga_skills(target: Path) -> int:
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
    print(f"Installed goga commands to {target}/commands/goga/", file=sys.stderr)
    print(f"Installed {len(commands)} commands: {', '.join(commands)}", file=sys.stderr)
    print(f"Installed goga skills to {target}/skills/", file=sys.stderr)
    print(f"Installed {len(skills)} skills: {', '.join(skills)}", file=sys.stderr)


def install(agent: str | None = None, config: Config = None) -> int:
    if config is None:
        print("Error: config is required", file=sys.stderr)
        return 1
    resolved_agent = agent if agent is not None else config.build.task_executor.agent

    try:
        target = _resolve_target_dir(resolved_agent)
    except ValueError:
        print(f"Error: unsupported agent '{resolved_agent}'", file=sys.stderr)
        return 1

    source = _get_source_dir()
    if not source.is_dir():
        print(f"Error: agent resources not found at {source}", file=sys.stderr)
        return 1

    target.mkdir(parents=True, exist_ok=True)

    try:
        _cleanup_goga_skills(target)
        commands = _install_commands(source, target)
        skills = _install_skills(source, target)
        _download_dsl_spec(target)
        _print_summary(commands, skills, target)
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0
