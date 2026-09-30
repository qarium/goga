from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable

import click
import yaml

from ...ast import AST
from ...ast.errors import DocumentParseError
from ...config import load_tool_config


def _build_ast() -> AST:
    """Construct and load the project AST at the current project root.

    Follows the `loading` practice: build `AST(".")` at the dispatcher's
    current working directory and call `.load()` to populate `.tree` and
    `.errors`. Validation rule violations are collected into `ast_obj.errors`
    and passed through to the tool unchanged — this builder never inspects or
    branches on them (see the CODEMANIFEST "Constraints"). A project root
    without a CODEMANIFEST leaves `.tree` and `.errors` empty. Structural
    failures — malformed YAML, unknown header/footer keys, non-list `Imports`,
    or an unreadable manifest — are raised by the provider's loader
    (`yaml.YAMLError` / `DocumentParseError`); this builder lets them propagate
    to the caller, and the `tool` command catches them and reports a clean error.

    Returns:
        The loaded AST instance for the current project root.

    Raises:
        DocumentParseError: If the manifest is structurally invalid (e.g. an
            unknown header/footer key or a non-list `Imports`).
        yaml.YAMLError: If the manifest file contains malformed YAML.
    """
    ast_obj = AST(".")
    ast_obj.load()

    return ast_obj


_OFFERED_INJECTIONS: dict[str, Callable[[str], object]] = {
    "ast": lambda _tool: _build_ast(),
    "config": lambda tool: load_tool_config(tool, "config.yml"),
}


def build_injections(main: Callable, tool: str) -> dict[str, object]:
    """Project main's signature against the offered injections, building each lazily.

    Examines the keyword-capable parameters of `main` and, for each whose name
    matches an injection the dispatcher can supply (see `_OFFERED_INJECTIONS`),
    builds the value lazily via the registered builder and collects it as a
    keyword argument to forward to the entry point.

    Only positional-or-keyword and keyword-only parameters are considered;
    positional-only, variadic positional, and variadic keyword parameters are
    skipped, as are parameters whose name is not offered. The `ast` injection is
    built only when `main` declares it, and the `config` injection — the raw
    parsed tool config of `tool` — only when `main` declares that. This is a
    pure transformation over the signature; it never inspects `ast.errors` and
    never interprets the config content.

    Args:
        main: The tool package entry callable.
        tool: The canonical tool identity — the hyphenated directory owner
            of the tool config files under `.goga/tools`; the dispatcher
            derives it from the dispatched module spelling
            (`goga_tool_hello_world` → `hello-world`).

    Returns:
        The keyword arguments to forward to the entry point. Empty when `main`
        declares no offered parameter; `{"ast": ast_obj}` when it declares
        `ast`; `{"config": data}` when it declares `config` — the raw parsed
        value, or `None` when the config file is absent (the normal state).

    Raises:
        DocumentParseError: When `main` declares `ast` and the project manifest
            is structurally invalid.
        yaml.YAMLError: When `main` declares `ast` and the manifest contains
            malformed YAML, or when `main` declares `config` and the tool
            config file fails to parse.
        OSError: When a declared source cannot be read.
        UnicodeDecodeError: When a declared source is not decodable as UTF-8.
    """
    injections: dict[str, object] = {}
    keyword_capable = {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}

    for param in inspect.signature(main).parameters.values():
        if param.kind not in keyword_capable:
            continue
        builder = _OFFERED_INJECTIONS.get(param.name)
        if builder is None:
            continue
        injections[param.name] = builder(tool)

    return injections


@click.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("name")
@click.pass_context
def tool(ctx: click.Context, name: str) -> None:
    """Run an external tool package by name.

    Runs the installed ``goga_tool_<name>`` package, forwarding any remaining
    arguments to it. Use the tool name without the ``goga_tool_`` prefix.
    """
    package_name = f"goga_tool_{name}"
    try:
        module = importlib.import_module(package_name)
    except ModuleNotFoundError as exc:
        # `importlib.import_module` raises ModuleNotFoundError both when the
        # requested package is genuinely absent and when the package exists but
        # a transitive import inside it fails. The import machinery records the
        # name of the module it could not resolve on `exc.name`, and that equals
        # `package_name` only when the tool package itself is missing. When a
        # deeper import failed, the package was found, so the misleading "not
        # found" message must not mask the real cause — re-raise and let the
        # honest traceback through, exactly like the `main` invocation below.
        if exc.name != package_name:
            raise
        click.secho(f"Tool package '{package_name}' not found", fg="red", err=True)
        ctx.exit(1)

    try:
        main_fn = module.main
    except AttributeError:
        click.secho(f"Tool package '{package_name}' has no 'main' function", fg="red", err=True)
        ctx.exit(1)

    # The canonical tool identity — the directory owner of the tool config
    # files — is the hyphen form: a multi-word package (`goga_tool_hello_world`)
    # dispatches under its importable underscore spelling, and the same
    # identity derivation the tools platform assigns everywhere else (hooks,
    # pipelines, skills) turns it into `hello-world`.
    identity = name.replace("_", "-")

    try:
        injections = build_injections(main_fn, identity)
    except (DocumentParseError, yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        click.secho(f"Failed to load project AST or tool config: {exc}", fg="red", err=True)
        ctx.exit(1)

    main_fn(list(ctx.args), **injections)
