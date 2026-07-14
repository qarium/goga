from __future__ import annotations

import logging
import subprocess
import sys

import click

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


def _install(name: str, use_sudo: bool = False, version: str | None = None) -> int:
    """Install a ``goga-tool-<name>`` package into the current interpreter via pip.

    Composes the PyPI-canonical dash-form package identifier from ``name``,
    raw-appends ``version`` when provided (no operator injection — the caller owns
    the operator), and invokes ``<sys.executable> -m pip install ... -U`` so the
    package lands in the same environment as goga. When ``use_sudo`` is set, the
    invocation runs under ``sudo --preserve-env=HOME`` so downstream tool discovery
    reads the caller's home. pip's returncode is returned verbatim (``check=False``);
    no translation, no wrapping, no ``CalledProcessError``.

    Args:
        name: Tool identifier without the ``goga-tool-`` / ``goga_tool_`` prefix.
        use_sudo: When True, run pip under ``sudo --preserve-env=HOME`` (Unix-only).
        version: Optional version specifier appended raw to the package identifier;
            the caller owns the operator. Default None.

    Returns:
        pip's returncode propagated as-is (0 success, non-zero failure).
    """
    logger.info("install start")
    if use_sudo:
        logger.warning("running pip under sudo")

    # 1. Compose the package identifier in its PyPI-canonical dash form from `name`.
    pkg_id = f"goga-tool-{name}"
    # 2. If `version` is set, append it verbatim to the identifier — no operator injection.
    if version is not None:
        pkg_id += version
    # 3. Invoke pip through the current interpreter; always request an upgrade
    #    so the command is idempotent for the already-installed case.
    argv: list[str] = [sys.executable, "-m", "pip", "install", pkg_id, "-U"]
    # 4. If `use_sudo` is set, run under sudo with HOME preserved so downstream
    #    tool discovery reads the caller's home directory.
    if use_sudo:
        argv = ["sudo", "--preserve-env=HOME", *argv]
    # 5. Return the invocation's returncode without translation.
    result = subprocess.run(argv, check=False)
    if result.returncode == 0:
        logger.info("install complete")
    else:
        logger.error("pip failed with exit code %s", result.returncode)
    return result.returncode


@click.command()
@click.argument("name")
@click.option("--sudo", is_flag=True, default=False, help="Run pip under sudo with --preserve-env=HOME")
@click.option(
    "--version",
    default=None,
    help="Version specifier appended raw to the package identifier (caller owns the operator)",
)
@click.pass_context
def install(ctx: click.Context, name: str, sudo: bool, version: str | None) -> None:
    """Install a goga-tool package into the current runtime interpreter via pip.

    Runs ``<python> -m pip install goga-tool-<name> -U`` against the interpreter
    running goga, optionally appending a raw version specifier and/or running under
    ``sudo --preserve-env=HOME``. pip's returncode is propagated as the exit code
    without translation — pip failures surface as a non-zero exit, never as a
    ``CalledProcessError``.

    Args:
        ctx: Click execution context used to control process exit codes.
        name: Tool identifier without the ``goga-tool-`` / ``goga_tool_`` prefix.
        sudo: When True, run pip under ``sudo --preserve-env=HOME``.
        version: Version specifier appended raw to the package identifier; the
            caller owns the operator.
    """
    ctx.exit(_install(name=name, use_sudo=sudo, version=version))
