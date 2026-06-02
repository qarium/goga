from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ..config import Config

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
    dsl_path.parent.mkdir(parents=True, exist_ok=True)
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


def _install_tool_skills(target: Path, force_overwrite: bool) -> list[str]:  # noqa: C901
    pkg_map = importlib.metadata.packages_distributions()
    tool_skills: list[str] = []
    for top_level_name in sorted(pkg_map):
        if not top_level_name.startswith("goga_tool_"):
            continue
        try:
            spec = importlib.util.find_spec(top_level_name)
        except (ModuleNotFoundError, ValueError):
            continue
        if spec is None or spec.origin is None:
            continue
        package_path = Path(spec.origin).parent
        tool_name = top_level_name.removeprefix("goga_tool_")
        if not (package_path / "skills" / tool_name / "SKILL.md").is_file():
            print(
                f"Warning: package {top_level_name} missing skills/{tool_name}/SKILL.md, skipping",
                file=sys.stderr,
            )
            continue
        try:
            skills_dir = package_path / "skills"
            for skill_entry in skills_dir.iterdir():
                if not skill_entry.is_dir():
                    continue
                dest = target / "skills" / f"goga-tool-{skill_entry.name}"
                if dest.exists():
                    if not force_overwrite:
                        print(
                            f"Warning: skill {dest.name} already exists, skipping",
                            file=sys.stderr,
                        )
                        continue
                    shutil.rmtree(dest)
                shutil.copytree(skill_entry, dest)
                if dest.name not in tool_skills:
                    tool_skills.append(dest.name)
        except (OSError, shutil.Error) as e:
            print(f"Warning: failed to install skills from {top_level_name}: {e}", file=sys.stderr)
    return tool_skills


def connect(agent: str | None = None, config: Config | None = None, force_overwrite: bool = False) -> int:
    """Connect goga agent commands, skills, and DSL spec to the target directory.

    Args:
        agent: Target agent name (e.g. 'claude'). If None, uses config.build.task_executor.agent.
        config: Project configuration. Required for resolving agent and settings.
        force_overwrite: Overwrite existing tool skills without prompting.

    Returns:
        0 on success, 1 on failure.
    """
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
        tool_skills = _install_tool_skills(target, force_overwrite)
        skills.extend(tool_skills)
        _print_summary(commands, skills, target)
    except (OSError, shutil.Error) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0
