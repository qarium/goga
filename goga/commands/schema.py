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
    return sorted(f.name for f in entries if f.suffix == ".md")


def _cell_in_set(doc: DocumentRoot, cells: frozenset[str]) -> bool:
    if os.path.normpath(doc.path) in cells:
        return True
    return any(_cell_in_set(child, cells) for child in doc.children)


def _build_dependencies(doc: DocumentRoot) -> dict:
    deps: dict[str, dict] = {}
    for item in doc.header.imports.types:
        path = os.path.normpath(item.from_path)
        deps.setdefault(path, {"types": set(), "usages": set()})
        deps[path]["types"].update(item.type_name)
    for item in doc.header.imports.usages:
        path = os.path.normpath(item.from_path)
        deps.setdefault(path, {"types": set(), "usages": set()})
        deps[path]["usages"].update(item.usage_name)
    return {
        path: {"types": sorted(data["types"]), "usages": sorted(data["usages"])}
        for path, data in sorted(deps.items())
    }


def _build_cell_tree(doc: DocumentRoot, allowed_cells: frozenset[str] | None = None) -> dict:
    children: list[dict] = []
    for child in doc.children:
        if allowed_cells is not None and not _cell_in_set(child, allowed_cells):
            continue
        children.append(_build_cell_tree(child, allowed_cells))

    return {
        "cell": os.path.normpath(doc.path),
        "description": doc.footer.description,
        "types": sorted([e.name for e in doc.body.entities] + [r.name for r in doc.body.routines]),
        "usages": _find_usages_files(doc.path),
        "dependencies": _build_dependencies(doc),
        "children": children,
    }


def _prune_depth(cell: dict, max_depth: int, current_depth: int = 0) -> dict:
    if current_depth >= max_depth:
        return {**cell, "children": []}
    return {
        **cell,
        "children": [_prune_depth(child, max_depth, current_depth + 1) for child in cell.get("children", [])],
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


def _has_dependency(cell_dict: dict, dep_paths: frozenset[str]) -> bool:
    if any(key in dep_paths for key in cell_dict.get("dependencies", {})):
        return True
    return any(_has_dependency(child, dep_paths) for child in cell_dict.get("children", []))


def _filter_by_depends_on(result: list[dict], depends_on: tuple[str, ...]) -> list[dict]:
    if not depends_on:
        return result
    dep_paths = frozenset(os.path.normpath(p) for p in depends_on)
    return [cell for cell in result if _has_dependency(cell, dep_paths)]


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
    ast_obj = AST(".")
    ast_obj.load()

    tree = _filter_tree(ast_obj.tree, cells)

    allowed = frozenset(os.path.normpath(c) for c in cells) if cells else None
    result = [_build_cell_tree(doc, allowed) for doc in tree]
    result = _filter_by_depends_on(result, depends_on)
    if max_depth is not None:
        result = [_prune_depth(cell, max_depth) for cell in result]
    json_str = json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
    click.echo(json_str)

    ctx.exit(1 if ast_obj.errors else 0)
