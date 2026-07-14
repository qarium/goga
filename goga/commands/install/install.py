from __future__ import annotations

import logging
import subprocess
import sys

import click
import yaml

from ...config import load_config

logger = logging.getLogger(__name__)

# Four-form version grammar — segment-count thresholds (see resolve_version).
# A version form splits on "." into segments; the segment count fixes the form:
#   2 segments → major x-range "N.x"; 3 segments with a trailing "x" → minor
#   x-range "N.M.x"; 1-3 numeric segments → concrete "N(.M)?(.K)?".
_XRANGE_MAJOR_SEGMENTS = 2
_XRANGE_MINOR_SEGMENTS = 3
_CONCRETE_MIN_SEGMENTS = 1
_CONCRETE_MAX_SEGMENTS = 3


def resolve_version(form: str | None) -> str | None:
    """Resolve a four-form version string into a pip specifier.

    Sole owner of the version grammar. Maps a version-form string to the pip
    specifier appended to a package identifier, or returns ``None`` when no
    specifier should be appended (the ``latest`` / absent case). Raises
    ``ValueError`` on operator-prefixed or malformed input — this routine owns
    the operator and emits it from the resolved grammar form.

    Accepted forms:
      * ``None`` or the literal ``"latest"`` → ``None`` (pip selects newest).
      * Major x-range ``"N.x"`` (one dot, last segment ``"x"``) → ``"~=N.0"``
        (PEP 440 compatible-release, upper bound ``<(N+1).0``).
      * Minor x-range ``"N.M.x"`` (two dots, last segment ``"x"``) → ``"~=N.M.0"``
        (PEP 440 compatible-release, upper bound ``<N.(M+1).0``). The trailing
        ``.0`` is required: ``~=N.M`` alone is a major-only bound.
      * Concrete ``"N"``, ``"N.M"``, or ``"N.M.K"`` (dot-separated non-empty
        numeric segments, no trailing ``"x"``) → ``"==<form>"``.

    Everything else — operator prefixes (``==``, ``>=``, ``<=``, ``~=``,
    ``!=``, ``<``, ``>``, ``===``), pre/post/local segments (``1.0.0a1``,
    ``1.0.0.post1``, ``1.0.0+local``), and any other shape — raises
    ``ValueError``. This is a pure transformer: no I/O, no logging, no config
    reading, no PEP 440 existence check (shape only).

    Args:
        form: Version-form string in one of the four grammar forms, or ``None``
            when no version was supplied.

    Returns:
        The resolved pip specifier (operator-prefixed), or ``None`` when the
        latest / no-specifier marker is requested.

    Raises:
        ValueError: If ``form`` is operator-prefixed or does not match any of
            the four grammar forms.
    """
    # 1. None / "latest" → no specifier; pip selects the newest under -U.
    if form is None or form == "latest":
        return None
    # 2. Operator-prefixed forms are rejected — this routine owns the operator.
    if form.startswith(("==", ">=", "<=", "~=", "!=", "<", ">", "===")):
        raise ValueError("operator-prefixed forms are rejected")
    segments = form.split(".")
    # 3. Major x-range "N.x": exactly one dot, last segment "x", major numeric.
    if (
        len(segments) == _XRANGE_MAJOR_SEGMENTS
        and segments[1] == "x"
        and segments[0].isdigit()
        and segments[0] != ""
    ):
        return f"~={segments[0]}.0"
    # 4. Minor x-range "N.M.x": exactly two dots, last segment "x", both numeric.
    if (
        len(segments) == _XRANGE_MINOR_SEGMENTS
        and segments[2] == "x"
        and segments[0].isdigit()
        and segments[1].isdigit()
    ):
        return f"~={segments[0]}.{segments[1]}.0"
    # 5. Concrete "N(.M)?(.K)?": 1-3 numeric segments, no trailing "x".
    if _CONCRETE_MIN_SEGMENTS <= len(segments) <= _CONCRETE_MAX_SEGMENTS and all(
        s.isdigit() and s != "" for s in segments
    ):
        return f"=={form}"
    # 6. Anything else is malformed.
    raise ValueError("malformed version form")


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


@click.command()
@click.argument("name", required=False)
@click.option("--sudo", is_flag=True, default=False, help="Run pip under sudo with --preserve-env=HOME")
@click.option(
    "--version",
    default=None,
    help="Version form for the tool (single-path only); resolved into a pip specifier",
)
@click.pass_context
def install(ctx: click.Context, name: str | None, sudo: bool, version: str | None) -> None:
    """Install goga-tool packages into the current interpreter via pip.

    Three paths, selected by whether ``name`` is given:

      * SINGLE (``name`` set): resolve ``version`` through the four-form grammar
        and install ``goga-tool-<name><spec>`` in one pip call.
      * BULK (``name`` omitted, ``.goga/config.yml`` lists ``tools:``): resolve
        every tool form in YAML insertion order and install all
        ``goga-tool-<tool><spec>`` identifiers in a single pip call.
      * EMPTY (``name`` omitted, no ``tools:``): print ``Nothing to install``
        and exit 0 without invoking pip.

    pip's returncode is propagated as the exit code without translation — pip
    failures surface as a non-zero exit, never as a ``CalledProcessError``.
    Errors from ``resolve_version`` and ``load_config`` surface as
    ``click.ClickException`` (exit 1).

    Args:
        ctx: Click execution context used to control process exit codes.
        name: Tool identifier without the ``goga-tool-`` prefix (single path).
            Omit to drive the bulk/empty path from ``.goga/config.yml``.
        sudo: When True, run pip under ``sudo --preserve-env=HOME``.
        version: Version form for the single path, resolved by ``resolve_version``.
    """
    if name is not None:
        # SINGLE PATH — install one tool, grammar-resolving --version.
        try:
            pkg = _resolve_pkg(name, version)
        except ValueError as exc:
            raise click.ClickException(f"invalid --version value {version!r}: {exc}") from exc
        ctx.exit(_run_pip(_pip_argv([pkg], sudo), sudo))

    # BULK / EMPTY PATH — driven by .goga/config.yml.
    try:
        cfg = load_config()
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
    ctx.exit(_run_pip(_pip_argv(pkgs, sudo), sudo))
