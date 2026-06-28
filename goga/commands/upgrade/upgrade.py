from __future__ import annotations

import importlib.metadata
import logging
import pwd
import subprocess
import sys
from pathlib import Path

import click
import yaml

from ...connect import connect

logger = logging.getLogger(__name__)


def _build_pip_command(include_tools: bool, use_sudo: bool) -> list[str]:
    """Build the pip upgrade command per Algorithm step 1.

    Always targets the current interpreter via the ``<python> -m pip`` form.
    Optionally appends discovered ``goga_tool_*`` distribution names and/or
    prefixes the command with ``sudo --preserve-env=HOME``.

    Args:
        include_tools: Append discovered ``goga_tool_*`` distribution names.
        use_sudo: Prefix the command with ``sudo --preserve-env=HOME``.

    Returns:
        The fully assembled pip command argv list.
    """
    cmd: list[str] = [sys.executable, "-m", "pip", "install", "goga", "-U"]
    if include_tools:
        pkg_map = importlib.metadata.packages_distributions()
        cmd.extend(name for name in sorted(pkg_map) if name.startswith("goga_tool_"))
    if use_sudo:
        cmd = ["sudo", "--preserve-env=HOME", *cmd]
    return cmd


def _resolve_goga_home(target_user: str | None) -> Path | None:
    """Resolve the ``~/.goga`` directory for the registry lookup (step 4).

    Returns ``None`` (and logs) when ``target_user`` is unknown to
    :func:`pwd.getpwnam` so the caller can surface a non-zero exit code without
    crashing on a bare ``KeyError``.

    Args:
        target_user: Optional username to resolve via :func:`pwd.getpwnam`.

    Returns:
        The resolved ``<home>/.goga`` path, or ``None`` on an unknown user.
    """
    if target_user is None:
        return Path.home() / ".goga"
    try:
        return Path(pwd.getpwnam(target_user).pw_dir) / ".goga"
    except KeyError:
        logger.error("unknown user '%s'", target_user)
        return None


def _read_connect_registry(connect_yml: Path) -> dict | None:
    """Load the ``connect.yml`` registry (step 5).

    A missing file is a normal condition (no agents connected yet) and yields an
    empty mapping so the re-sync loop is a no-op. A YAML parse error is logged
    and signals failure to the caller via ``None``.

    Args:
        connect_yml: Path to the registry file.

    Returns:
        The parsed registry mapping (possibly empty), or ``None`` on parse error.
    """
    if not connect_yml.exists():
        return {}
    try:
        loaded = yaml.safe_load(connect_yml.read_text())
    except yaml.YAMLError as exc:
        logger.error("failed to parse %s: %s", connect_yml, exc)
        return None
    return loaded if isinstance(loaded, dict) else {}


def _resync_agents(registry: dict) -> int:
    """Re-sync every agent in the registry, returning the first failure (step 6).

    Each agent's own ``force_overwrite`` is read from the registry and forwarded
    to :func:`connect`; remaining agents are still processed after a failure so a
    single bad agent does not skip the rest.

    Args:
        registry: The parsed ``connect.yml`` mapping.

    Returns:
        The first non-zero agent exit code, or ``0`` if all agents succeeded.
    """
    agents = registry.get("agents", {})
    if not isinstance(agents, dict):
        return 0

    first_failure = 0
    for agent_name, entry in agents.items():
        per_agent_force = bool(entry.get("force_overwrite", False)) if isinstance(entry, dict) else False
        rc = connect(agents=[agent_name], force_overwrite=per_agent_force)
        if rc != 0 and first_failure == 0:
            first_failure = rc
    return first_failure


def _upgrade(use_sudo: bool = False, target_user: str | None = None, include_tools: bool = False) -> int:
    """Upgrade goga via pip then re-sync agents from the ``connect.yml`` registry.

    Runs ``pip install goga -U`` (optionally with discovered ``goga_tool_*``
    packages and/or under ``sudo --preserve-env=HOME``), then re-syncs every agent
    recorded in ``<goga_home>/connect.yml`` using each agent's persisted
    ``force_overwrite`` value (never hardcoded).

    Args:
        use_sudo: Prepend ``sudo --preserve-env=HOME`` to the pip command for
            system-Python installs requiring root.
        target_user: Resolve ``~/.goga`` for this username via
            :func:`pwd.getpwnam` instead of ``$HOME``.
        include_tools: Also upgrade discovered ``goga_tool_*`` packages.

    Returns:
        0 on success, the pip exit code on pip failure, or the first non-zero
        agent re-sync failure.
    """
    logger.info("upgrade start")
    if use_sudo:
        logger.warning("running pip under sudo")

    cmd = _build_pip_command(include_tools=include_tools, use_sudo=use_sudo)
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        logger.error("pip failed with exit code %s", result.returncode)
        return result.returncode

    goga_home = _resolve_goga_home(target_user)
    if goga_home is None:
        return 1

    registry = _read_connect_registry(goga_home / "connect.yml")
    if registry is None:
        return 1

    first_failure = _resync_agents(registry)
    if first_failure != 0:
        logger.error("re-sync failed with exit code %s", first_failure)
    else:
        logger.info("upgrade complete")
    return first_failure


@click.command()
@click.option("--sudo", is_flag=True, default=False, help="Run pip under sudo with --preserve-env=HOME")
@click.option("--user", default=None, help="Re-sync this user's ~/.goga via pwd.getpwnam")
@click.option("--tools", is_flag=True, default=False, help="Also upgrade installed goga_tool_* packages")
@click.pass_context
def upgrade(ctx: click.Context, sudo: bool, user: str | None, tools: bool) -> None:
    """Upgrade goga (and optionally goga_tool_* packages) then re-sync agents.

    Runs ``pip install goga -U`` on the current interpreter, then re-syncs every
    agent recorded in ``~/.goga/connect.yml`` using each agent's persisted
    ``force_overwrite`` setting. Use ``--user`` to re-sync another user's goga
    installation and ``--sudo`` for system-Python installs requiring root.

    Args:
        ctx: Click execution context used to control process exit codes.
        sudo: When True, run pip under ``sudo --preserve-env=HOME``.
        user: When set, resolve ``~/.goga`` for this username via
            :func:`pwd.getpwnam`.
        tools: When True, also upgrade discovered ``goga_tool_*`` packages.
    """
    ctx.exit(_upgrade(use_sudo=sudo, target_user=user, include_tools=tools))
