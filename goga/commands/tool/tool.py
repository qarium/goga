from __future__ import annotations

import importlib
import inspect
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


def build_injections(main: Callable) -> dict[str, object]:
    """Project main's signature against the offered injections, building each lazily.

    Examines the keyword-capable parameters of `main` and, for each whose name
    matches an injection the dispatcher can supply (see `_OFFERED_INJECTIONS`),
    builds the value lazily via the registered builder and collects it as a
    keyword argument to forward to the entry point.

    Only positional-or-keyword and keyword-only parameters are considered;
    positional-only, variadic positional, and variadic keyword parameters are
    skipped, as are parameters whose name is not offered. The `ast` injection is
    built only when `main` declares it. This is a pure transformation:
    `Callable -> dict[str, object]`; it never inspects `ast.errors`.

    Args:
        main: The tool package entry callable.

    Returns:
        The keyword arguments to forward to the entry point. Empty when `main`
        declares no offered parameter; `{"ast": ast_obj}` when it declares `ast`.
    """
    injections: dict[str, object] = {}
    keyword_capable = {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    for param in inspect.signature(main).parameters.values():
        if param.kind not in keyword_capable:
            continue
        builder = _OFFERED_INJECTIONS.get(param.name)
        if builder is None:
            continue
        injections[param.name] = builder()
    return injections


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
