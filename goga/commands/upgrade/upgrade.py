from __future__ import annotations

import importlib.metadata
import logging
import pwd
import subprocess
import sys
from pathlib import Path

import click

from ...connect import resync_registered_agents

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
        # Identify tool packages by their importable module name (``goga_tool_*``),
        # but pass pip the *distribution* name (the value) — pip resolves by
        # distribution name, not top-level module name.
        for module_name in sorted(pkg_map):
            if module_name.startswith("goga_tool_"):
                cmd.extend(pkg_map[module_name])
    if use_sudo:
        cmd = ["sudo", "--preserve-env=HOME", *cmd]
    return cmd


def _resolve_goga_home(target_user: str | None) -> Path | None:
    """Resolve the ``~/.goga`` directory for activation (Algorithm step 4a/4b).

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
    except (KeyError, OSError):
        # KeyError: unknown user. OSError: backend lookup failure (e.g. NIS/LDAP).
        # Either way the user cannot be resolved — surface a non-zero exit, do not crash.
        logger.error("unknown user '%s'", target_user)
        return None


def _upgrade(use_sudo: bool = False, target_user: str | None = None, include_tools: bool = False) -> int:
    """Upgrade goga via pip then delegate agent re-sync to the shared routine.

    Runs ``pip install goga -U`` (optionally with discovered ``goga_tool_*``
    packages and/or under ``sudo --preserve-env=HOME``), then resolves the
    owning user's ``~/.goga`` and delegates the registry re-sync to
    :func:`resync_registered_agents`, which reads ``<goga_home>/connect.yml``,
    re-activates every recorded agent with that agent's persisted
    ``force_overwrite``, and redirects ``$HOME`` to the owning home internally
    (D1) so ``connect()`` targets the correct installation.

    Args:
        use_sudo: Prepend ``sudo --preserve-env=HOME`` to the pip command for
            system-Python installs requiring root.
        target_user: Resolve ``~/.goga`` for this username via
            :func:`pwd.getpwnam` instead of ``$HOME``.
        include_tools: Also upgrade discovered ``goga_tool_*`` packages.

    Returns:
        0 on success, the pip exit code on pip failure, ``1`` when
        ``target_user`` is unknown, or the activation outcome (first non-zero
        per-agent failure) from the delegated re-sync.
    """
    logger.info("upgrade start")
    if use_sudo:
        logger.warning("running pip under sudo")

    cmd = _build_pip_command(include_tools=include_tools, use_sudo=use_sudo)
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        logger.error("pip failed with exit code %s", result.returncode)
        return result.returncode

    # 4. Resolve the owning user's ~/.goga; an unknown target_user is a hard fail.
    goga_home = _resolve_goga_home(target_user)
    if goga_home is None:
        return 1

    # 5-6. Delegate activation (registry read + per-agent connect + $HOME override
    #      via D1) to the shared routine — upgrade never reads connect.yml itself.
    outcome = resync_registered_agents(goga_home)
    if outcome != 0:
        logger.error("re-sync failed with exit code %s", outcome)
    else:
        logger.info("upgrade complete")
    return outcome


@click.command()
@click.option("--sudo", is_flag=True, default=False, help="Run pip under sudo with --preserve-env=HOME")
@click.option("--user", default=None, help="Re-sync this user's ~/.goga via pwd.getpwnam")
@click.option("--tools", is_flag=True, default=False, help="Also upgrade installed goga_tool_* packages")
@click.pass_context
def upgrade(ctx: click.Context, sudo: bool, user: str | None, tools: bool) -> None:
    """Upgrade goga (and optionally goga_tool_* packages) then re-sync agents.

    Runs ``pip install goga -U`` on the current interpreter, then re-syncs every
    agent recorded in ``~/.goga/connect.yml`` by delegating to the shared
    :func:`resync_registered_agents` routine, which re-applies each agent's
    persisted ``force_overwrite`` setting. Use ``--user`` to re-sync another
    user's goga installation and ``--sudo`` for system-Python installs requiring
    root.

    Args:
        ctx: Click execution context used to control process exit codes.
        sudo: When True, run pip under ``sudo --preserve-env=HOME``.
        user: When set, resolve ``~/.goga`` for this username via
            :func:`pwd.getpwnam`.
        tools: When True, also upgrade discovered ``goga_tool_*`` packages.
    """
    ctx.exit(_upgrade(use_sudo=sudo, target_user=user, include_tools=tools))
