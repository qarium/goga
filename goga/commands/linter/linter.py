from __future__ import annotations

import os

import click
import yaml

from ...ast import AST
from ...ast.ast import _flatten_tree


@click.command()
@click.argument("path", default=".")
@click.pass_context
def linter(ctx: click.Context, path: str) -> None:
    """Validate CODEMANIFEST files in the project."""
    os.chdir(path)

    ast_obj = AST(".")
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
    summary = f"goga linter\n-------------------------\ncells: {cell_count} errors: {error_count}"
    click.echo(summary)
    ctx.exit(1 if error_count > 0 else 0)
