from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import click

from ..ast import AST

if TYPE_CHECKING:
    from ..ast.nodes import DocumentRoot


def _find_usages_files(doc_path: str) -> list[str]:
    usages_dir = Path(doc_path) / ".usages"
    try:
        entries = list(usages_dir.iterdir())
    except OSError:
        return []
    return sorted(os.path.normpath(str(f)) for f in entries if f.suffix == ".md")


def _cell_in_set(doc: DocumentRoot, cells: frozenset[str]) -> bool:
    if os.path.normpath(doc.path) in cells:
        return True
    return any(_cell_in_set(child, cells) for child in doc.children)


def _build_cell_tree(
    doc: DocumentRoot, max_depth: int | None, current_depth: int, allowed_cells: frozenset[str] | None = None,
) -> dict:
    children: list[dict] = []
    if max_depth is None or current_depth < max_depth:
        for child in doc.children:
            if allowed_cells is not None and not _cell_in_set(child, allowed_cells):
                continue
            children.append(_build_cell_tree(child, max_depth, current_depth + 1, allowed_cells))

    return {
        "cell": os.path.normpath(doc.path),
        "description": doc.footer.description,
        "usages": _find_usages_files(doc.path),
        "relations": sorted(
            {
                os.path.normpath(item.from_path)
                for item in doc.header.imports.types + doc.header.imports.usages
            }
        ),
        "children": children,
    }


def _filter_tree(tree: list[DocumentRoot], cells: tuple[str, ...]) -> list[DocumentRoot]:
    if not cells:
        return tree

    normalized_cells = {os.path.normpath(c) for c in cells}

    def _flatten(docs: list[DocumentRoot]) -> list[DocumentRoot]:
        result: list[DocumentRoot] = []
        for doc in docs:
            result.append(doc)
            result.extend(_flatten(doc.children))
        return result

    all_docs = _flatten(tree)
    matching_paths = {os.path.normpath(doc.path) for doc in all_docs if os.path.normpath(doc.path) in normalized_cells}

    def _root_matches(root: DocumentRoot) -> bool:
        if os.path.normpath(root.path) in matching_paths:
            return True
        return any(_root_matches(child) for child in root.children)

    return [root for root in tree if _root_matches(root)]


@click.command()
@click.argument("cells", nargs=-1)
@click.option("--max-depth", type=int, default=None)
@click.pass_context
def schema(
    ctx: click.Context,
    cells: tuple[str, ...],
    max_depth: int | None,
) -> None:
    """Output project CODEMANIFEST schema as JSON tree.

    Walks the current directory tree for CODEMANIFEST files,
    builds a hierarchical JSON structure and prints it to stdout.

    \b
    JSON structure per root cell:
      cell         - normalized path to the CODEMANIFEST folder
      description  - text from the footer Description section
      usages       - list of .md files found in <path>/.usages/
      relations    - sorted unique normalized import paths (from Imports)
      children     - nested child cells (same structure, recursively)

    \b
    Options:
      cells          - zero or more cell paths to filter output (variadic)
      --max-depth N  - limit nesting depth of children (default: unlimited)

    Exit codes: 0 on success, 1 if AST parsing errors found.
    """
    ast_obj = AST(".")
    ast_obj.load()

    tree = _filter_tree(ast_obj.tree, cells)

    allowed = frozenset(os.path.normpath(c) for c in cells) if cells else None
    result = [_build_cell_tree(doc, max_depth, 0, allowed) for doc in tree]
    json_str = json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
    click.echo(json_str)

    ctx.exit(1 if ast_obj.errors else 0)
