from __future__ import annotations

import json

import click
import yaml

from ...config import load_project_config
from ...config.hooks import ConfigHooks
from ...schema import schema as schema_logic
from ...schema.hooks import SchemaNode


def _project_node(node: SchemaNode) -> dict:
    """Project one read-only schema node onto the family JSON output shape."""
    projected = {
        "cell": node.path,
        "description": node.description,
        "types": list(node.types),
        "usages": list(node.usages),
        "dependencies": {dep.path: {"types": list(dep.types), "usages": list(dep.usages)} for dep in node.dependencies},
        "children": [_project_node(child) for child in node.children],
    }

    if node.tools:
        projected["tools"] = node.tools

    return projected


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
      tools         - tool contributions of the cell-amendment checkpoint,
                      present iff at least one tool wrote at least one fact
    """
    ignore: list[str] | None = None

    # Config is optional for the schema command: the loader try keeps
    # lint's swallow semantics — an absent or invalid .goga/config.yml
    # runs the generation unfiltered, and nothing was loaded, so no
    # checkpoint is offered.
    try:
        cfg = load_project_config()
    except (OSError, KeyError, ValueError, yaml.YAMLError):
        cfg = None

    if cfg is not None:
        # The delivery runs outside the swallowing try, in its own
        # wrapper: a hard checkpoint failure stops the command with a
        # clean error — never treated as "config absent".
        try:
            overlay = ConfigHooks().amend_config(config=cfg)
        except (ValueError, ImportError) as exc:
            # ImportError — a broken tool package facade during the
            # registry build — is the same clean error, never a raw
            # traceback.
            raise click.ClickException(str(exc)) from exc

        for line in overlay.summary_lines:
            click.echo(line, err=True)

        ignore = None if overlay.config.lint is None else overlay.config.lint.ignore

    try:
        result = schema_logic(list(cells), max_depth, list(depends_on), ignore=ignore)
    except Exception as e:
        click.echo(str(e), err=True)
        ctx.exit(1)
    click.echo(json.dumps([_project_node(n) for n in result], indent=4, sort_keys=True, ensure_ascii=False))
