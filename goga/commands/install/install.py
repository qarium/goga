from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import click
import yaml

from ...config import load_project_config
from ...config.hooks import ConfigHooks
from ...connect import resync_registered_agents
from ...version import resolve_version
from .hook import run_install_hooks

logger = logging.getLogger(__name__)


def _pip_argv(pkgs: list[str], sudo: bool) -> list[str]:
    """Compose the ``pip install`` argv for one or more package identifiers.

    Args:
        pkgs: Package identifiers to install.
        sudo: Prepend ``sudo --preserve-env=HOME`` so downstream tool
            discovery still reads the caller's home directory.

    Returns:
        The argv running pip through the current interpreter (the package
        lands in the same environment as goga), always requesting an
        upgrade (``-U``) for idempotency.
    """
    argv: list[str] = [sys.executable, "-m", "pip", "install", *pkgs, "-U"]

    if sudo:
        argv = ["sudo", "--preserve-env=HOME", *argv]

    return argv


def _run_pip(argv: list[str], sudo: bool) -> int:
    """Invoke pip with ``argv`` and return its returncode verbatim.

    Args:
        argv: The pip invocation, already composed by ``_pip_argv``.
        sudo: When True, the run is logged as running under sudo.

    Returns:
        The returncode, propagated without translation — ``check=False``
        means a non-zero returncode surfaces here, never as a
        ``CalledProcessError``.

    Raises:
        click.ClickException: when the executable cannot be started
            (``OSError``: a missing binary such as ``sudo``, or a
            present-but-non-executable one raising ``PermissionError``) —
            there is no returncode to propagate.
    """
    logger.info("install start", extra={"packages": argv})

    if sudo:
        logger.info("running pip under sudo", extra={"packages": argv})

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
        logger.info("install complete", extra={"packages": argv, "returncode": result.returncode})
    else:
        logger.error("pip failed", extra={"packages": argv, "returncode": result.returncode})

    return result.returncode


def _resolve_pkg(name: str, form: str | None) -> str:
    """Resolve ``form`` and compose the ``goga-tool-<name><spec>`` identifier.

    Args:
        name: Tool name without the ``goga-tool-`` prefix.
        form: Version form to resolve, or ``None``.

    Returns:
        The composed ``goga-tool-<name><spec>`` identifier.

    Raises:
        ValueError: propagated from ``resolve_version`` for a rejected
            form; the caller wraps it in a ``click.ClickException``.
    """
    spec = resolve_version(form)
    return f"goga-tool-{name}" + (spec or "")


def _parse_local(value: str) -> tuple[str, str | None]:
    """Split a ``--local`` value into its path and optional tool-name suffix.

    Args:
        value: The raw ``--local`` option value — ``<path>`` or
            ``<path>:<tool-name>``; the suffix names the tool whose
            post-install hook runs for the local install, without it no
            hook runs.

    Returns:
        The local directory path and the tool name from the suffix (the
        FIRST colon is the separator), or ``None`` when the value carries
        no ``:`` suffix.

    Raises:
        click.ClickException: when the suffix is malformed — an empty name,
            a path separator, or another colon (e.g. a Windows drive path
            misread as a suffix); a user-facing error (exit 1) raised
            before any pip invocation.
    """
    path, sep, tool = value.partition(":")
    if sep == "":
        return value, None
    if tool == "":
        raise click.ClickException(f"malformed --local value {value!r}: empty tool name after ':'")
    if "/" in tool or "\\" in tool:
        raise click.ClickException(f"malformed --local value {value!r}: tool name must not contain a path separator")
    if ":" in tool:
        raise click.ClickException(f"malformed --local value {value!r}: tool name must not contain ':'")

    return path, tool


def _local_hook_targets(local_path: str, local_tool: str | None) -> list[str]:
    """Compose the LOCAL path's hook-target list (Algorithm step 2.2).

    Args:
        local_path: The local directory path from the ``--local`` value.
        local_tool: The tool name from the ``:<tool-name>`` suffix, or None
            when the value carries no suffix.

    Returns:
        The hook-target list handed to the hooks step — ``[<tool>]`` with a
        suffix, or an empty list without one (no tool name is guessed from
        the path; a warning names the suffix as the way to enable the
        hook).
    """
    if local_tool is None:
        logger.warning(
            "install hook skipped for local source",
            extra={"path": local_path, "hint": "pass :<tool-name> to enable the post-install hook"},
        )
        return []

    return [local_tool]


def _resolve_bulk_pkgs(tools: dict[str, str]) -> list[str]:
    """Resolve every declared tool's identifier, preserving insertion order.

    Args:
        tools: The config tools mapping, in YAML insertion order.

    Returns:
        The composed ``goga-tool-<name><spec>`` identifiers.

    Raises:
        click.ClickException: when a tool's version form is rejected — the
            message names the offending tool; raised before any pip
            invocation.
    """
    pkgs: list[str] = []

    for tool_name, form in tools.items():
        try:
            pkgs.append(_resolve_pkg(tool_name, form))
        except ValueError as exc:
            raise click.ClickException(f"invalid version for tool {tool_name!r}: {exc}") from exc

    return pkgs


def _after_pip(pip_rc: int, hook_targets: list[str], no_connect: bool) -> int:
    """Run the post-install hooks and activation after pip (Algorithm steps 4 and 5).

    Args:
        pip_rc: The exit code returned by the pip invocation; hooks and
            activation run only when it is 0.
        hook_targets: Names of the freshly installed tools in installation
            order — the per-path hook target list (single ``[name]``, local
            ``[<tool>]`` or empty, bulk config keys).
        no_connect: When True, skip activation (the agent re-sync) and keep
            ``pip_rc`` verbatim — the hooks already ran.

    Returns:
        ``pip_rc`` when hooks or activation are skipped, otherwise the re-sync
        outcome (0 on full success or a missing/empty registry, else the first
        non-zero per-agent failure).

    Raises:
        click.ClickException: when the hooks step fails — hooks run in
            installation order, one initiating user, stopping at the first
            failure; a wrapped hook failure carries the tool name and hook
            message, an unwrapped hook-step failure (e.g. identity
            resolution) surfaces its own message. The pip package stays in
            place and activation never runs. ``BaseException`` (Ctrl-C,
            SystemExit) is never caught.

    Note:
        The re-sync targets the current user's ``~/.goga`` and is the single
        path through which activation runs; this routine never writes
        ``connect.yml`` and never runs under sudo.
    """
    if pip_rc != 0:
        # Nothing runs after a failed pip — no hooks, no re-sync.
        return pip_rc

    try:
        run_install_hooks(hook_targets)
    except Exception as exc:
        # The wrapped RuntimeError carries the tool name; an unwrapped
        # hook-step failure (identity resolution) surfaces here equally clean.
        raise click.ClickException(str(exc)) from exc

    if no_connect:
        # The flag suppresses only the re-sync; the hooks already ran.
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
    help=(
        "Path to a pip-installable local directory, optionally :<tool-name> "
        "to name the tool whose install hook runs; mutually exclusive with "
        "name; --version is rejected"
    ),
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
        exclusive with ``name``, and ``--version`` is rejected. The value may
        carry a ``:<tool-name>`` suffix naming the tool whose post-install
        hook runs; without it no hook runs for the local install.
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

    local_path: str | None = None
    local_tool: str | None = None

    if local is not None:
        # 0.3. VALIDATION — the :<tool-name> suffix grammar; a malformed suffix
        # aborts before any pip, a well-formed one names the hook target.
        local_path, local_tool = _parse_local(local)

    if name is not None:
        # SINGLE PATH — install one tool, grammar-resolving --version.
        try:
            pkg = _resolve_pkg(name, version)
        except ValueError as exc:
            raise click.ClickException(f"invalid --version value {version!r}: {exc}") from exc

        pip_rc = _run_pip(_pip_argv([pkg], sudo), sudo)
        ctx.exit(_after_pip(pip_rc, [name], no_connect))

    if local is not None:
        # LOCAL PATH — pip-install a local directory. pip owns the missing-path
        # error (no CLI-level existence check), and -U is always requested (never -e).
        hook_targets = _local_hook_targets(local_path, local_tool)
        pip_rc = _run_pip(_pip_argv([local_path], sudo), sudo)
        ctx.exit(_after_pip(pip_rc, hook_targets, no_connect))

    # BULK / EMPTY PATH — driven by .goga/config.yml.
    try:
        authored = load_project_config()
        # The config-amendment checkpoint joins the load inside the try: a
        # hard checkpoint failure is the same clean error as a failed load.
        # Only the bulk path loads the config — the single and local paths
        # install without any checkpoint.
        overlay = ConfigHooks().amend_config(config=authored)
    except (OSError, KeyError, ValueError, ImportError, yaml.YAMLError) as exc:
        # OSError covers every failure to read .goga/config.yml: a missing file
        # (FileNotFoundError), a path that is a directory (IsADirectoryError), or
        # an unreadable file (PermissionError). ImportError — a broken tool
        # package facade during the registry build — is the same clean error,
        # never a raw traceback. All must surface as a clean error.
        raise click.ClickException(str(exc)) from exc

    for line in overlay.summary_lines:
        click.echo(line, err=True)

    # The installed set derives from the effective tools mapping.
    effective = overlay.config
    tools = effective.tools if effective.tools is not None else {}

    if not tools:
        click.echo("Nothing to install")
        ctx.exit(0)

    pkgs = _resolve_bulk_pkgs(tools)
    pip_rc = _run_pip(_pip_argv(pkgs, sudo), sudo)
    ctx.exit(_after_pip(pip_rc, list(tools.keys()), no_connect))
