from __future__ import annotations

import json
from dataclasses import asdict

import click

from ...codegraph import codegraph as codegraph_logic
from ...codegraph.facts import CodegraphNode


@click.command()
@click.argument("cells", nargs=-1)
@click.option("--max-depth", type=int, default=None)
@click.option("--depends-on", multiple=True, help="Filter cells by dependency on specified cell paths")
@click.pass_context
def codegraph(
    ctx: click.Context,
    cells: tuple[str, ...],
    max_depth: int | None,
    depends_on: tuple[str, ...],
) -> None:
    """Output the prospective cell graph of existing code as JSON tree.

    Parses the project's source files with tree-sitter, groups them into
    directory units, resolves cross-unit imports, and prints the resulting
    cell tree to stdout.

    Every diagnostic goes to stderr; stdout carries the JSON document only.

    \b
    JSON structure per root cell:
      cell          - normalized path of the directory unit
      types         - sorted facade type names of the unit — its exported
                      names under the language visibility rules
      dependencies  - dict grouping imported facade types by normalized
                      target cell path, each value is the sorted list of
                      that unit's types imported by the cell
      children      - nested child cells (same structure, recursively)
    """
    try:
        result: list[CodegraphNode] = codegraph_logic(list(cells), max_depth, list(depends_on))
    except Exception as e:
        click.echo(str(e), err=True)
        ctx.exit(1)
    click.echo(json.dumps([asdict(n) for n in result], indent=4, sort_keys=True, ensure_ascii=False))
