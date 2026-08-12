from __future__ import annotations

import os

import click
import yaml

from ...ast import AST
from ...ast.ast import _flatten_tree
from ...config import load_project_config


@click.command()
@click.argument("path", default=".")
@click.pass_context
def lint(ctx: click.Context, path: str) -> None:
    """Validate CODEMANIFEST files in the project.

    Loads the AST for the target path, prints each validation error with its
    source location, and emits a cell/error count summary.
    """
    os.chdir(path)

    ignore: list[str] | None = None

    try:
        cfg = load_project_config()
        ignore = None if cfg.lint is None else cfg.lint.ignore
    except (OSError, KeyError, ValueError, yaml.YAMLError):
        ignore = None

    ast_obj = AST(".", ignore=ignore)
    ast_obj.load()

    for error in ast_obj.errors:
        rule_line = click.style(f"[{error.rule}]", fg="red")
        click.echo(f"{rule_line} {error.message}")

        doc_path = getattr(error.document, "path", None) if error.document else None
        if doc_path is not None:
            click.echo(f"  --> {doc_path}")

        if error.node is not None and hasattr(error.node, "data") and error.node.data is not None:
            click.echo("      ---")

            yaml_str = yaml.dump(
                error.node.data,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
                indent=2,
            )
            for line in yaml_str.splitlines():
                click.echo(f"      {line}")

    click.echo("")

    cell_count = len(_flatten_tree(ast_obj.tree))
    error_count = len(ast_obj.errors)
    summary = f"goga lint\n-------------------------\ncells: {cell_count} errors: {error_count}"
    click.echo(summary)

    ctx.exit(1 if error_count > 0 else 0)
