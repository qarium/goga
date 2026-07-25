from __future__ import annotations

import importlib
from collections.abc import Callable

import click

from ...ast import AST


def _build_ast() -> AST:
    """Construct and load the project AST at the current project root.

    Follows the `loading` practice: build `AST(".")` at the dispatcher's
    current working directory and call `.load()` to populate `.tree` and
    `.errors`. Missing or invalid manifests populate `ast_obj.errors` rather
    than raising, so this builder does not inspect or branch on errors.

    Returns:
        The loaded AST instance for the current project root.
    """
    ast_obj = AST(".")
    ast_obj.load()
    return ast_obj


_OFFERED_INJECTIONS: dict[str, Callable[[], object]] = {"ast": _build_ast}


@click.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("name")
@click.pass_context
def tool(ctx: click.Context, name: str) -> None:
    """Run an external tool package by name.

    Imports the package `goga_tool_<name>` and invokes its `main` entrypoint
    with the remaining CLI arguments.

    Args:
        ctx: Click execution context used to forward extra args and exit codes.
        name: Identifier of the tool package to run (without the `goga_tool_`
            prefix).
    """
    package_name = f"goga_tool_{name}"
    try:
        module = importlib.import_module(package_name)
    except ModuleNotFoundError:
        click.secho(f"Tool package '{package_name}' not found", fg="red", err=True)
        ctx.exit(1)

    try:
        main_fn = module.main
    except AttributeError:
        click.secho(f"Tool package '{package_name}' has no 'main' function", fg="red", err=True)
        ctx.exit(1)

    main_fn(list(ctx.args))
