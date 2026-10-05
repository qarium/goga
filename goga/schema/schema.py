from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from ..ast import AST
from ..ast.ast import _flatten_tree
from .hooks import CellFacts, DependencyFacts, SchemaHooks, SchemaNode
from .hooks.events import _copy_json

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
        path: {"types": sorted(data["types"]), "usages": sorted(data["usages"])} for path, data in sorted(deps.items())
    }


def _build_dependency_facts(doc: DocumentRoot) -> list[DependencyFacts]:
    return [
        DependencyFacts(path=path, types=data["types"], usages=data["usages"])
        for path, data in _build_dependencies(doc).items()
    ]


def _type_names(doc: DocumentRoot) -> list[str]:
    return sorted([e.name for e in doc.body.entities] + [r.name for r in doc.body.routines])


def _build_cell_tree(doc: DocumentRoot, allowed_cells: frozenset[str] | None = None) -> dict:
    children: list[dict] = []
    for child in doc.children:
        if allowed_cells is not None and not _cell_in_set(child, allowed_cells):
            continue
        children.append(_build_cell_tree(child, allowed_cells))

    return {
        "cell": os.path.normpath(doc.path),
        "description": doc.footer.description,
        "types": _type_names(doc),
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


def _filter_tree(tree: list[DocumentRoot], cells: list[str]) -> list[DocumentRoot]:
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


def _prune_by_dependency(cell_dict: dict, dep_paths: frozenset[str]) -> dict:
    kept_children = [
        _prune_by_dependency(child, dep_paths)
        for child in cell_dict.get("children", [])
        if _has_dependency(child, dep_paths)
    ]
    return {**cell_dict, "children": kept_children}


def _filter_by_depends_on(result: list[dict], depends_on: list[str]) -> list[dict]:
    if not depends_on:
        return result
    dep_paths = frozenset(os.path.normpath(p) for p in depends_on)
    return [_prune_by_dependency(cell, dep_paths) for cell in result if _has_dependency(cell, dep_paths)]


def _walk_nodes(nodes: list[dict]) -> Iterator[dict]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node["children"])


def _to_schema_node(node: dict) -> SchemaNode:
    """Project one node of the final dict tree onto the gate's read-only record.

    Args:
        node: one serialized cell node of the final tree — the six base
            fields plus the committed tools overlay when one exists.

    Returns:
        The :class:`~goga.schema.hooks.SchemaNode` projection of ``node`` — every field rebuilt,
            so no value written later reaches the serialized tree.
    """
    return SchemaNode(
        path=node["cell"],
        description=node["description"],
        types=list(node["types"]),
        usages=list(node["usages"]),
        dependencies=[
            DependencyFacts(path=path, types=list(data["types"]), usages=list(data["usages"]))
            for path, data in node["dependencies"].items()
        ],
        children=[_to_schema_node(child) for child in node["children"]],
        tools={tool: _copy_json(facts) for tool, facts in node.get("tools", {}).items()},
    )


def schema(cells: list[str], max_depth: int | None, depends_on: list[str]) -> str:
    """Build a JSON schema tree of cells from the project AST — amended per cell, gated once before serialization.

    Args:
        cells: List of cell paths to include. Empty list includes all cells.
        max_depth: Maximum nesting depth for the cell tree. None means unlimited.
        depends_on: Filter cells to those depending on the specified paths.

    Returns:
        JSON string representing the filtered cell tree — a node's ``tools`` key is present iff at
        least one tool wrote at least one fact on it; an emptied tree returns ``"[]"`` before any checkpoint.

    Raises:
        ValueError: If the AST has parsing errors, a checkpoint hard
            failure stops the walk — the message names the tool, the
            action, and the failing cell path — or the validation gate
            vetoed the final tree — the message lists every violation,
            one line per tool and hook.
        ImportError: If a tool package facade fails to import — the
            message names the package.
    """
    ast_obj = AST(".")
    ast_obj.load()

    if ast_obj.errors:
        raise ValueError(f"AST parsing failed with {len(ast_obj.errors)} error(s)")

    tree = _filter_tree(ast_obj.tree, cells)

    allowed = frozenset(os.path.normpath(c) for c in cells) if cells else None
    result = [_build_cell_tree(doc, allowed) for doc in tree]
    result = _filter_by_depends_on(result, depends_on)

    if max_depth is not None:
        result = [_prune_depth(cell, max_depth) for cell in result]

    if not result:
        return "[]"

    nodes = {node["cell"]: node for node in _walk_nodes(result)}
    hooks = SchemaHooks()

    for doc in _flatten_tree(ast_obj.tree):
        path = os.path.normpath(doc.path)
        if path not in nodes:
            continue

        facts = CellFacts(
            path=path,
            description=doc.footer.description,
            types=_type_names(doc),
            usages=_find_usages_files(doc.path),
            dependencies=_build_dependency_facts(doc),
            children=[os.path.normpath(child.path) for child in doc.children],
        )
        tools = hooks.amend_cell(cell=facts)
        if tools:
            nodes[path]["tools"] = tools

    verdict = hooks.validate_schema([_to_schema_node(node) for node in result])
    if not verdict.approved:
        details = "\n".join(
            f"- tool {violation.tool} / hook {violation.hook}: {violation.reason}" for violation in verdict.violations
        )
        raise ValueError(f"schema validation failed:\n{details}")

    return json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
