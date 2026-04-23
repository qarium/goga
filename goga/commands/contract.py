"""Compare CODEMANIFEST contracts with Python source implementation.

Outputs a JSON object mapping each cell path to its CODEMANIFEST
and source sides for comparison.

\b
JSON structure per cell:
  codemanifest  - contract declarations from CODEMANIFEST files
  source        - extracted Python source contracts

Exit codes: 0 on success, 1 if AST parsing errors found.
"""

from __future__ import annotations

import json

import click

from ..ast import AST
from ..comparator import compare as compare_contracts


@click.command()
@click.argument("paths", nargs=-1)
@click.pass_context
def contract(ctx: click.Context, paths: tuple[str, ...]) -> None:
    """Output CODEMANIFEST vs source comparison as JSON."""
    ast_obj = AST(".")
    ast_obj.load()

    result = compare_contracts(ast_obj.tree, list(paths))
    json_str = json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
    click.echo(json_str)

    ctx.exit(1 if ast_obj.errors else 0)
