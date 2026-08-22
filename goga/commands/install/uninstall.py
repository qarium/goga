from __future__ import annotations

import logging
import pwd
import subprocess
import sys
from pathlib import Path

import click

from ...connect import resync_registered_agents

logger = logging.getLogger(__name__)


def _pip_argv(name: str, sudo: bool) -> list[str]:
    """Compose the ``pip uninstall`` argv for exactly one tool identifier.

    Runs pip through the current interpreter so the package is removed from
    the same environment goga runs in, always passes the force flag ``-y``
    (the interaction stays at the command-level confirmation prompt — pip
    never asks), and prepends ``sudo --preserve-env=HOME`` when ``sudo`` is
    set so downstream re-sync discovery still reads the caller's home
    directory.
    """
    argv: list[str] = [sys.executable, "-m", "pip", "uninstall", "-y", f"goga-tool-{name}"]

    if sudo:
        argv = ["sudo", "--preserve-env=HOME", *argv]

    return argv


def _run_pip(argv: list[str], sudo: bool) -> int:
    """Invoke pip with ``argv`` and return its returncode verbatim.

    pip's returncode is propagated without translation — ``check=False`` means
    a non-zero returncode surfaces here, never as a ``CalledProcessError``;
    pip's own "not installed" skip (``Skipping ... as it is not installed``)
    is a WARNING with exit code 0 and therefore counts as success. Any failure
    to start the executable (``OSError``: a missing binary such as ``sudo`` on
    a host without it, or a present-but-non-executable one raising
    ``PermissionError``) is translated to a ``click.ClickException`` (exit 1)
    since there is no returncode to propagate.
    """
    logger.info("uninstall start")

    if sudo:
        logger.warning("running pip under sudo")

    try:
        result = subprocess.run(argv, check=False)
    except OSError as exc:
        # The executable named at argv[0] could not be started (``FileNotFoundError``
        # when it's missing — e.g. ``--sudo`` on a host without sudo, or an
        # unreachable interpreter; ``PermissionError`` when present but not
        # executable). Name the actual binary so the user knows what to install —
        # ``exc.strerror`` alone ("No such file or directory") would mislead when
        # sudo, not pip, is what's absent.
        target = exc.filename or argv[0]
        raise click.ClickException(f"failed to start {target}: {exc.strerror or exc}") from exc

    if result.returncode == 0:
        logger.info("uninstall complete")
    else:
        logger.error("pip failed with exit code %s", result.returncode)

    return result.returncode


def _resolve_goga_home(target_user: str | None) -> Path:
    """Resolve the ``~/.goga`` directory for the post-removal re-sync.

    Unlike the upgrade variant — which reports an unknown user only after pip
    has already run — this resolution happens before any side effect (the
    confirmation prompt included), so an unresolvable ``target_user`` aborts
    via ``click.ClickException`` with nothing removed.

    Args:
        target_user: Optional username to resolve via :func:`pwd.getpwnam`.

    Returns:
        The resolved ``<home>/.goga`` path for the current or target user.

    Raises:
        click.ClickException: When ``target_user`` cannot be resolved —
            always before the prompt, pip, and any re-sync.
    """
    if target_user is None:
        return Path.home() / ".goga"

    try:
        return Path(pwd.getpwnam(target_user).pw_dir) / ".goga"
    except (KeyError, OSError) as exc:
        # KeyError: unknown user. OSError: backend lookup failure (e.g. NIS/LDAP).
        # Either way nothing has been removed yet — fail fast with a clean error.
        logger.error("unknown user '%s'", target_user)
        raise click.ClickException(f"unknown user '{target_user}'") from exc


@click.command()
@click.argument("name")
@click.option("--sudo", is_flag=True, default=False, help="Run pip under sudo with --preserve-env=HOME")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip the removal confirmation prompt")
@click.option("--user", "target_user", default=None, help="Re-sync this user's ~/.goga directory")
@click.pass_context
def uninstall(
    ctx: click.Context,
    name: str,
    sudo: bool = False,
    yes: bool = False,
    target_user: str | None = None,
) -> None:
    """Remove a goga-tool package from the current interpreter via pip.

    Asks for confirmation before pip runs — Enter removes, "n" cancels;
    --yes / -y skips the prompt. After a successful pip uninstall every
    connected agent is re-synced so the removed tool's skills and pipelines
    disappear from ~/.goga/. The pip exit code propagates unchanged.
    """
    # 0. VALIDATIONS — resolve (and validate) the re-sync home before the
    #    confirmation prompt and any side effect: an unknown --user removes nothing.
    goga_home = _resolve_goga_home(target_user)

    # 1. CONFIRMATION — the default answer is Y: Enter continues, an explicit
    #    "n" cancels with a message and exit 0, a closed stdin aborts non-zero.
    if not yes and not click.confirm(f'Remove goga tool "{name}"?', default=True):
        click.echo(f'Removal of goga tool "{name}" cancelled')
        ctx.exit(0)

    # 2-3. pip — exactly one forced uninstall of goga-tool-<name>; a non-zero
    #      returncode is final and suppresses the re-sync.
    pip_rc = _run_pip(_pip_argv(name, sudo), sudo)
    if pip_rc != 0:
        ctx.exit(pip_rc)

    # 4-5. RE-SYNC — the removal's artifact-cleanup mechanism; it never runs
    #      under sudo, and its outcome is the final exit code.
    outcome = resync_registered_agents(goga_home)
    if outcome != 0:
        logger.error("re-sync failed with exit code %s", outcome)

    ctx.exit(outcome)
