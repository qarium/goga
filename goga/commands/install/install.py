from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import click
import yaml

from ...config import load_project_config
from ...connect import resync_registered_agents
from ...version import resolve_version

logger = logging.getLogger(__name__)


def _pip_argv(pkgs: list[str], sudo: bool) -> list[str]:
    """Compose the ``pip install`` argv for one or more package identifiers.

    Runs pip through the current interpreter so the package lands in the same
    environment as goga, always requests an upgrade (``-U``) for idempotency,
    and prepends ``sudo --preserve-env=HOME`` when ``sudo`` is set so downstream
    tool discovery still reads the caller's home directory.
    """
    argv: list[str] = [sys.executable, "-m", "pip", "install", *pkgs, "-U"]

    if sudo:
        argv = ["sudo", "--preserve-env=HOME", *argv]

    return argv


def _run_pip(argv: list[str], sudo: bool) -> int:
    """Invoke pip with ``argv`` and return its returncode verbatim.

    pip's returncode is propagated without translation — ``check=False`` means a
    non-zero returncode surfaces here, never as a ``CalledProcessError``. Any
    failure to start the executable (``OSError``: a missing binary such as
    ``sudo`` on a host without it, or a present-but-non-executable one raising
    ``PermissionError``) is translated to a ``click.ClickException`` (exit 1)
    since there is no returncode to propagate.
    """
    logger.info("install start")

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
        logger.info("install complete")
    else:
        logger.error("pip failed with exit code %s", result.returncode)

    return result.returncode


def _resolve_pkg(name: str, form: str | None) -> str:
    """Resolve ``form`` and compose the ``goga-tool-<name><spec>`` identifier.

    A ``ValueError`` from ``resolve_version`` propagates to the caller, which
    wraps it in a ``click.ClickException``.
    """
    spec = resolve_version(form)
    return f"goga-tool-{name}" + (spec or "")


def _after_pip(pip_rc: int, no_connect: bool) -> int:
    """Decide the final exit code after pip (Algorithm step 4 — ACTIVATION).

    Activation (the post-install agent re-sync) runs only when pip succeeded
    (``pip_rc == 0``) and the caller did not opt out with ``no_connect``. When
    skipped — because pip failed or ``no_connect`` is set — pip's own outcome is
    the final exit code. The re-sync targets the current user's ``~/.goga`` and
    is the single path through which activation runs; this routine never writes
    ``connect.yml`` and never runs under sudo.

    Args:
        pip_rc: The exit code returned by the pip invocation.
        no_connect: When True, skip activation and keep ``pip_rc`` verbatim.

    Returns:
        ``pip_rc`` when activation is skipped, otherwise the re-sync outcome
        (0 on full success or a missing/empty registry, else the first
        non-zero per-agent failure).
    """
    if no_connect or pip_rc != 0:
        return pip_rc

    return resync_registered_agents(Path.home() / ".goga")


@click.command()
@click.argument("name", required=False)
@click.option("--sudo", is_flag=True, default=False, help="Run pip under sudo with --preserve-env=HOME")
@click.option(
    "--version",
    "-v",
    default=None,
    help="Version form for the tool (single-path only); resolved into a pip specifier",
)
@click.option(
    "--local",
    "-l",
    "local",
    default=None,
    help="Path to a pip-installable local directory (local mode); mutually exclusive with name; --version is rejected",
)
@click.option(
    "--no-connect",
    "no_connect",
    is_flag=True,
    default=False,
    help="Skip post-install agent activation (install-only)",
)
@click.pass_context
def install(  # noqa: PLR0913, PLR0917 — Click callback arity is contract-mandated
    ctx: click.Context,
    name: str | None,
    sudo: bool,
    version: str | None,
    local: str | None,
    no_connect: bool = False,
) -> None:
    """Install goga-tool packages into the current interpreter via pip.

    Four paths, selected by whether ``name`` or ``--local`` is given:

    \b
      * SINGLE (``name`` set): install ``goga-tool-<name><spec>`` resolved from
        ``--version`` in a single pip call.
      * LOCAL (``--local <path>`` set): pip-install a local directory; mutually
        exclusive with ``name``, and ``--version`` is rejected.
      * BULK (``name`` omitted, ``.goga/config.yml`` lists ``tools:``): install
        every ``goga-tool-<tool><spec>`` declared in the config in a single pip
        call.
      * EMPTY (``name`` omitted, no ``tools:``): print ``Nothing to install``
        and exit 0 without invoking pip.

    The pip exit code is propagated unchanged. Configuration or version errors
    exit with code 1.
    """
    # 0. VALIDATIONS — mutexes fire only when BOTH are set.
    if name is not None and local is not None:
        raise click.ClickException("name and --local are mutually exclusive")
    if local is not None and version is not None:
        raise click.ClickException("--version is not supported with --local")

    if name is not None:
        # SINGLE PATH — install one tool, grammar-resolving --version.
        try:
            pkg = _resolve_pkg(name, version)
        except ValueError as exc:
            raise click.ClickException(f"invalid --version value {version!r}: {exc}") from exc

        pip_rc = _run_pip(_pip_argv([pkg], sudo), sudo)
        ctx.exit(_after_pip(pip_rc, no_connect))

    if local is not None:
        # LOCAL PATH — pip-install a local directory. pip owns the missing-path
        # error (no CLI-level existence check), and -U is always requested (never -e).
        pip_rc = _run_pip(_pip_argv([local], sudo), sudo)
        ctx.exit(_after_pip(pip_rc, no_connect))

    # BULK / EMPTY PATH — driven by .goga/config.yml.
    try:
        cfg = load_project_config()
    except (OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        # OSError covers every failure to read .goga/config.yml: a missing file
        # (FileNotFoundError), a path that is a directory (IsADirectoryError), or
        # an unreadable file (PermissionError). All must surface as a clean error.
        raise click.ClickException(str(exc)) from exc

    tools = cfg.tools if cfg.tools is not None else {}
    if not tools:
        click.echo("Nothing to install")
        ctx.exit(0)

    pkgs: list[str] = []
    for tool_name, form in tools.items():
        try:
            pkgs.append(_resolve_pkg(tool_name, form))
        except ValueError as exc:
            raise click.ClickException(f"invalid version for tool {tool_name!r}: {exc}") from exc

    pip_rc = _run_pip(_pip_argv(pkgs, sudo), sudo)
    ctx.exit(_after_pip(pip_rc, no_connect))
