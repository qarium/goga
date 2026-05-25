from __future__ import annotations

import importlib

import click


@click.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("name")
@click.pass_context
def tool(ctx: click.Context, name: str) -> None:
    """Run an external tool package by name."""
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
