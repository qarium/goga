from __future__ import annotations

import click

from ...schema import schema as schema_logic


@click.command()
@click.argument("cells", nargs=-1)
@click.option("--max-depth", type=int, default=None)
@click.option("--depends-on", multiple=True, help="Filter cells by dependency on specified cell paths")
@click.pass_context
def schema(
    ctx: click.Context,
    cells: tuple[str, ...],
    max_depth: int | None,
    depends_on: tuple[str, ...],
) -> None:
    """Output project CODEMANIFEST schema as JSON tree.

    Walks the current directory tree for CODEMANIFEST files,
    builds a hierarchical JSON structure and prints it to stdout.

    \b
    JSON structure per root cell:
      cell          - normalized path to the CODEMANIFEST folder
      description   - text from the footer Description section
      types         - sorted list of entity and routine names from body
      usages        - list of .md filenames found in <path>/.usages/
      dependencies  - dict grouping imports by normalized from_path,
                      each value has "types" and "usages" lists
      children      - nested child cells (same structure, recursively)

    \b
    Options:
      cells          - zero or more cell paths to filter output (variadic)
      --max-depth N  - limit nesting depth of children (default: unlimited)
      --depends-on   - filter cells by dependency on specified cell paths (repeatable)

    Exit codes: 0 on success, 1 if AST parsing errors found.
    """
    try:
        result = schema_logic(list(cells), max_depth, list(depends_on))
        click.echo(result)
    except ValueError as e:
        click.echo(str(e), err=True)
        ctx.exit(1)
