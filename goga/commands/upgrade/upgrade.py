from __future__ import annotations

import importlib.metadata
import logging
import pwd
import subprocess
import sys
from pathlib import Path

import click

from ...connect import resync_registered_agents
from ...version import resolve_relative_spec

logger = logging.getLogger(__name__)


def _build_pip_command(goga_identifier: str, include_tools: bool, use_sudo: bool) -> list[str]:
    """Build the pip upgrade command per Algorithm step 1.

    Always targets the current interpreter via the ``<python> -m pip`` form.
    Optionally appends discovered ``goga_tool_*`` distribution names and/or
    prefixes the command with ``sudo --preserve-env=HOME``.

    Args:
        goga_identifier: pip identifier of the goga package — the bare
            ``"goga"``, or ``"goga<spec>"`` when a version-line flag is active;
            the specifier constrains only goga, never ``goga_tool_*``.
        include_tools: Append discovered ``goga_tool_*`` distribution names.
        use_sudo: Prefix the command with ``sudo --preserve-env=HOME``.

    Returns:
        The fully assembled pip command argv list.
    """
    cmd: list[str] = [sys.executable, "-m", "pip", "install", goga_identifier, "-U"]
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


def _upgrade(
    use_sudo: bool = False,
    target_user: str | None = None,
    include_tools: bool = False,
    patch_line: bool = False,
    minor_line: bool = False,
) -> int:
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
        patch_line: Constrain goga to the latest patch of the installed minor
            line (``~=X.Y.0``); mutually exclusive with ``minor_line``.
        minor_line: Constrain goga to the latest release within the installed
            major line (``~=X.0``); mutually exclusive with ``patch_line``.

    Returns:
        0 on success, the pip exit code on pip failure, ``1`` when
        ``target_user`` is unknown, or the activation outcome (first non-zero
        per-agent failure) from the delegated re-sync.

    Raises:
        click.ClickException: When both line flags are selected, when the
            installed goga version cannot be read in this interpreter, or when
            the version line cannot be resolved from it — always before pip
            runs (exit 1, no side effects).
    """
    # 0. VALIDATIONS — before logger.info and any side effect (pip, re-sync,
    #    metadata read). The mutex fires first so a contradictory invocation
    #    never touches the interpreter's package metadata at all.
    if patch_line and minor_line:
        raise click.ClickException("--patch and --minor are mutually exclusive")

    goga_identifier = "goga"
    if patch_line or minor_line:
        # Caller owns the metadata boundary: read the installed base first,
        # then resolve the line. An unreadable base is a hard fail — never a
        # silent fallback to latest.
        try:
            base = importlib.metadata.version("goga")
        except importlib.metadata.PackageNotFoundError as exc:
            raise click.ClickException("cannot determine the installed goga version in this interpreter") from exc
        if not base:
            # A broken dist-info (missing or headerless METADATA) makes
            # importlib.metadata.version return None instead of raising — the
            # same undeterminable-base contract applies, never a TypeError.
            raise click.ClickException("cannot determine the installed goga version in this interpreter")
        try:
            spec = resolve_relative_spec(base, patch=patch_line, minor=minor_line)
        except ValueError as exc:
            raise click.ClickException(f"cannot resolve the version line: {exc}") from exc
        goga_identifier = f"goga{spec}"

    logger.info("upgrade start")
    if use_sudo:
        logger.warning("running pip under sudo")

    cmd = _build_pip_command(goga_identifier, include_tools=include_tools, use_sudo=use_sudo)
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
@click.option("--user", default=None, help="Re-sync this user's ~/.goga directory")
@click.option("--tools", is_flag=True, default=False, help="Also upgrade installed goga_tool_* packages")
@click.option(
    "--patch",
    is_flag=True,
    default=False,
    help="Constrain goga to the latest patch of the installed minor line",
)
@click.option(
    "--minor",
    is_flag=True,
    default=False,
    help="Constrain goga to the latest release within the installed major line",
)
@click.pass_context
def upgrade(  # noqa: PLR0913, PLR0917 — Click callback arity is contract-mandated
    ctx: click.Context,
    sudo: bool,
    user: str | None,
    tools: bool,
    patch: bool,
    minor: bool,
) -> None:
    """Upgrade goga (and optionally goga_tool_* packages) then re-sync agents.

    Runs ``pip install goga -U`` on the current interpreter, then re-syncs every
    agent recorded in ``~/.goga/connect.yml`` with its persisted settings. Use
    ``--user`` to re-sync another user's goga installation and ``--sudo`` for
    system-Python installs requiring root. Use ``--patch`` / ``--minor`` to stay
    within the installed version's minor / major line.
    """
    ctx.exit(_upgrade(use_sudo=sudo, target_user=user, include_tools=tools, patch_line=patch, minor_line=minor))
