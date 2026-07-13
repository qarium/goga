from __future__ import annotations

import logging
import subprocess
import sys

import click

logger = logging.getLogger(__name__)


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
