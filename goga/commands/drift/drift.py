from __future__ import annotations

import json

import click

from ...drift import DriftEntry
from ...drift import drift as drift_logic


def _project_entry(entry: DriftEntry) -> dict:
    """Project one drift entry onto the family JSON output shape."""
    projected = {"kind": entry.kind, "cell": entry.cell}

    if entry.types is not None:
        projected["types"] = list(entry.types)

    return projected


@click.command()
@click.argument("cells", nargs=-1)
@click.option("--max-depth", type=int, default=None)
@click.option("--depends-on", multiple=True, help="Filter cells by dependency on specified cell paths")
@click.pass_context
def drift(
    ctx: click.Context,
    cells: tuple[str, ...],
    max_depth: int | None,
    depends_on: tuple[str, ...],
) -> None:
    """Report contract drift between declared manifests and actual code.

    Compares the declared contract view (goga schema) with the code-derived
    view (goga codegraph) and prints the flat JSON report of their
    structural discrepancies to stdout. Discrepancies are computed on the
    complete views; the filters scope the report only.

    Every diagnostic goes to stderr; stdout carries the JSON report only.

    \b
    JSON report entries (sorted by cell path then kind):
      kind   - "schema_only" or "codegraph_only"
      cell   - normalized path of the discrepancy subject
      types  - sorted type names missing from the other view; present
               only on type-level entries — its absence marks a
               cell-level discrepancy

    \b
    Exit codes:
      0 - comparison completed, no discrepancies
      1 - comparison completed, discrepancies found
      2 - comparison could not be performed
    """
    try:
        report = drift_logic(list(cells), max_depth, list(depends_on))
    except Exception as e:
        click.echo(str(e), err=True)
        ctx.exit(2)
    click.echo(json.dumps([_project_entry(entry) for entry in report], indent=4, sort_keys=True, ensure_ascii=False))
    if report:
        ctx.exit(1)
