from __future__ import annotations

import contextlib
import importlib.metadata
import importlib.util
import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import requests
import yaml

from .install_pipelines import install_pipelines

AGENT_DIRS: dict[str, str] = {
    "claude": ".claude",
    "codex": ".codex",
    "cursor": ".cursor",
    "opencode": ".config/opencode",
    "qwen": ".qwen",
}

AGENTS_WITH_COMMANDS: frozenset[str] = frozenset({"claude", "opencode", "qwen"})

DSL_SPEC_URL = "https://raw.githubusercontent.com/qarium/codemanifest/refs/heads/0.0.x/specs/en.md"


def _resolve_target_dir(agent: str) -> Path:
    if agent not in AGENT_DIRS:
        raise ValueError(f"Unsupported agent: {agent}")
    return Path.home() / AGENT_DIRS[agent]


def _get_source_dir() -> Path:
    return Path(__file__).parent.parent / "assets"


def _download_dsl_spec(target: Path) -> None:
    dsl_path = target / "skills" / "goga-cell" / "dsl.md"
    try:
        response = requests.get(DSL_SPEC_URL, timeout=30)
        response.raise_for_status()
        data = response.content
    except requests.exceptions.HTTPError as e:
        raise OSError(f"Failed to download DSL spec: HTTP {e.response.status_code} {e.response.reason}") from e
    except requests.exceptions.RequestException as e:
        raise OSError(f"Failed to download DSL spec: {e}") from e

    dsl_path.parent.mkdir(parents=True, exist_ok=True)
    dsl_path.write_bytes(data)


def _cleanup_goga_skills(target: Path) -> int:
    """Remove every ``goga-*`` entry under ``target/skills/``, including stale or broken symlinks.

    Args:
        target: Agent directory containing the ``skills/`` tree to clean.

    Returns:
        Number of removed entries.
    """
    target_skills = target / "skills"
    if not target_skills.is_dir():
        return 0

    removed = 0
    for entry in list(target_skills.iterdir()):
        if not entry.name.startswith("goga-"):
            continue
        if entry.is_symlink():
            entry.unlink()
        elif entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
        removed += 1

    return removed


def _print_summary(commands: list[str], skills: list[str], target: Path) -> None:
    if commands:
        print(f"Installed goga commands to {target}/commands/", file=sys.stderr)
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


def _install_central(goga_home: Path, source: Path, force_overwrite: bool) -> tuple[list[str], list[str]]:
    """Install central assets into ``goga_home`` (Algorithm step 3), returning ``(commands, skills)``.

    Args:
        goga_home: Central goga directory receiving the assets.
        source: Source assets directory shipped with the package.
        force_overwrite: Overwrite existing tool skills instead of skipping them.

    Returns:
        Tuple of installed command names and sorted skill names.
    """
    central_skills = goga_home / "skills"
    central_commands = goga_home / "commands"

    # 3.1 — purge central goga-* skills and commands (fully recreate).
    _cleanup_goga_skills(goga_home)
    shutil.rmtree(central_commands, ignore_errors=True)

    # 3.2 — copy commands centrally (only symlinked by agents that consume commands).
    shutil.copytree(source / "commands", central_commands)
    commands = sorted(p.stem for p in central_commands.glob("*.md"))

    # 3.3 — copy each source skill centrally.
    central_skills.mkdir(parents=True, exist_ok=True)
    skills: list[str] = []
    for entry in (source / "skills").iterdir():
        if not entry.is_dir():
            continue
        dest = central_skills / entry.name
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(entry, dest)
        skills.append(entry.name)

    # 3.4 — download DSL spec into the central goga-cell skill.
    _download_dsl_spec(goga_home)

    # 3.5 — install tool skills centrally.
    skills.extend(_install_tool_skills(goga_home, force_overwrite))

    return commands, sorted(skills)


def _safe_symlink(link: Path, real_target: Path) -> None:
    """Create symlink ``link`` → ``real_target``, replacing an existing link; ``OSError`` is logged, not raised.

    Args:
        link: Symlink path to create.
        real_target: Directory the link points to.
    """
    if link.is_symlink():
        link.unlink()
    try:
        link.symlink_to(real_target)
    except OSError as e:
        print(f"Error: failed to create symlink {link}: {e}", file=sys.stderr)


def _purge_commands_goga(target: Path) -> None:
    """Remove ``target/commands/goga`` whether it is a symlink or a real dir.

    Args:
        target: Agent directory containing the ``commands/`` tree.
    """
    cmd_goga = target / "commands" / "goga"
    if cmd_goga.is_symlink():
        cmd_goga.unlink()
    elif cmd_goga.is_dir():
        shutil.rmtree(cmd_goga)


def _create_agent_symlinks(agent: str, target: Path, goga_home: Path) -> None:
    """Purge stale agent-side entries and symlink into ``goga_home`` (step 4); purge failures are hard errors.

    Args:
        agent: Agent name deciding whether commands are symlinked.
        target: Agent-specific directory to activate.
        goga_home: Central goga directory symlinked into.
    """
    central_skills = goga_home / "skills"

    target.mkdir(parents=True, exist_ok=True)

    # 4.3 — pattern-matching purge of stale goga-* skills (dirs + symlinks).
    _cleanup_goga_skills(target)
    if agent in AGENTS_WITH_COMMANDS:
        _purge_commands_goga(target)

    # 4.4 — symlink every central goga-* skill into the agent dir.
    target_skills = target / "skills"
    target_skills.mkdir(parents=True, exist_ok=True)
    for entry in central_skills.iterdir():
        if entry.name.startswith("goga-") and entry.is_dir():
            _safe_symlink(target_skills / entry.name, entry)

    # 4.4 — for claude, symlink commands/goga into the central commands dir.
    if agent in AGENTS_WITH_COMMANDS:
        target_commands = target / "commands"
        target_commands.mkdir(parents=True, exist_ok=True)
        _safe_symlink(target_commands / "goga", goga_home / "commands")


def _write_connect_registry(goga_home: Path, agents: list[str], force_overwrite: bool) -> None:
    """Atomically update ``~/.goga/connect.yml`` with per-agent records (step 6), preserving other agents' entries.

    Args:
        goga_home: Central goga directory holding ``connect.yml``.
        agents: Agent names to record in the registry.
        force_overwrite: Flag persisted with each agent record.
    """
    connect_yml = goga_home / "connect.yml"
    registry: dict = {}
    if connect_yml.exists():
        loaded = yaml.safe_load(connect_yml.read_text())
        if isinstance(loaded, dict):
            registry = loaded

    registry.setdefault("agents", {})
    for agent in agents:
        registry["agents"][agent] = {"force_overwrite": force_overwrite}

    yaml_text = yaml.dump(
        registry,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        indent=2,
    )

    fd, tmp_name = tempfile.mkstemp(dir=goga_home, suffix=".tmp")
    tmp_file = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(yaml_text)
        tmp_file.replace(connect_yml)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_file.unlink()
        raise


def _validate_agents(agents: list[str], source: Path) -> int | None:
    """Pre-flight validation before any filesystem mutation, returning ``1`` on failure or ``None`` when valid.

    Args:
        agents: Requested agent names; must be non-empty and supported.
        source: Source assets directory shipped with the package.

    Returns:
        ``1`` on any validation failure, ``None`` when valid.
    """
    if not agents:
        print("Error: at least one agent is required", file=sys.stderr)
        return 1

    if not source.is_dir():
        print(f"Error: agent resources not found at {source}", file=sys.stderr)
        return 1

    for agent in agents:
        try:
            _resolve_target_dir(agent)
        except ValueError:
            print(f"Error: unsupported agent '{agent}'", file=sys.stderr)
            return 1

    return None


def connect(agents: list[str], force_overwrite: bool = False) -> int:
    """Install goga assets centrally into ``~/.goga/`` and symlink each agent in.

    Args:
        agents: List of target agent names (e.g. ['claude']); must not be empty.
        force_overwrite: Overwrite existing tool skills without prompting;
            forwarded to the pipeline install.

    Returns:
        0 on success, 1 on failure.
    """
    source = _get_source_dir()
    error = _validate_agents(agents, source)
    if error is not None:
        return error

    goga_home = Path.home() / ".goga"
    goga_home.mkdir(parents=True, exist_ok=True)

    # Step 3 — central install.
    try:
        commands, skills = _install_central(goga_home, source, force_overwrite)
    except (OSError, shutil.Error) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Step 4 — per-agent purge + symlinks (symlink OSError is non-fatal).
    for agent in agents:
        print(f"Connecting agent: {agent}", file=sys.stderr)
        target = _resolve_target_dir(agent)
        try:
            _create_agent_symlinks(agent, target, goga_home)
        except (OSError, shutil.Error) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Step 5 — pipelines (propagate force_overwrite; propagate exit code).
    pipelines_dir = goga_home / "pipelines"
    if install_pipelines(pipelines_dir, force_overwrite=force_overwrite) != 0:
        return 1

    # Step 6 — atomic registry update.
    _write_connect_registry(goga_home, agents, force_overwrite)

    summary_commands = commands if any(a in AGENTS_WITH_COMMANDS for a in agents) else []
    _print_summary(summary_commands, skills, goga_home)

    return 0


@contextlib.contextmanager
def _home_override(target_home: Path) -> Iterator[None]:
    """Point ``$HOME`` at ``target_home`` for the duration of the block; always restored on exit, even on error.

    Args:
        target_home: Directory to set as ``$HOME`` inside the block.

    Returns:
        Context manager yielding None with ``$HOME`` overridden.
    """
    saved = os.environ.get("HOME")
    os.environ["HOME"] = str(target_home)
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = saved


def resync_registered_agents(goga_home: Path) -> int:
    """Re-apply activation to every agent recorded in ``connect.yml``, forwarding each persisted ``force_overwrite``.

    Args:
        goga_home: Directory containing ``connect.yml`` (typically ``~/.goga``);
            ``$HOME`` is pointed at its parent while agents re-sync.

    Returns:
        ``0`` when every agent re-synced or the registry is missing/empty;
        otherwise the first non-zero per-agent exit code. A malformed or
        unreadable registry fails non-zero.
    """
    # 1-2. No registry yet — no agents connected, re-sync is a no-op.
    connect_yml = goga_home / "connect.yml"
    if not connect_yml.exists():
        return 0

    # 3. Parse; a malformed or unreadable registry is a hard failure (non-zero).
    try:
        loaded = yaml.safe_load(connect_yml.read_text())
    except FileNotFoundError:
        # Vanished between the existence check and the read — treat it as the
        # "missing registry" normal condition (return 0), per the contract.
        return 0
    except (yaml.YAMLError, OSError, UnicodeError) as exc:
        print(f"failed to parse {connect_yml}: {exc}", file=sys.stderr)
        return 1

    # 4. A non-mapping registry, or a missing/empty agents map, is a no-op.
    if not isinstance(loaded, dict):
        return 0
    agents = loaded.get("agents", {})
    if not isinstance(agents, dict) or not agents:
        return 0

    # 5. Emit a one-line banner so the user can tell a re-sync from a direct
    #    ``goga connect`` and see which agents are about to be processed.
    agent_names = ", ".join(agents.keys())
    print(f"Re-syncing {len(agents)} registered agent(s): {agent_names}", file=sys.stderr)

    # 6. Re-sync each agent under a $HOME override pointing at the owning home,
    #    forwarding each agent's own force_overwrite. Continue after a failure
    #    and remember only the first non-zero result.
    first_failure = 0
    with _home_override(goga_home.parent):
        for agent_name, entry in agents.items():
            per_agent_force = bool(entry.get("force_overwrite", False)) if isinstance(entry, dict) else False
            rc = connect(agents=[agent_name], force_overwrite=per_agent_force)
            if rc != 0 and first_failure == 0:
                first_failure = rc

    # 7. Return the first non-zero result, or 0 on full success.
    return first_failure
