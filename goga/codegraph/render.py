"""Graph rendering — node tree assembly, schema-parity filters, serialization.

Nests the flat units by their paths with structural compression — only cell
units carry output nodes, a non-cell unit survives solely as an ancestor that
a nested cell attaches through. The links aggregate into per-node
dependencies, the three schema-compatible filters apply in order, and the
resulting record tree serializes via ``beautiful_json``. Input records are
never modified — every filter rebuilds fresh nodes.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .facts import CellLink, CodegraphNode, Unit


def _with_children(node: CodegraphNode, children: list[CodegraphNode]) -> CodegraphNode:
    """Rebuild ``node`` with new children — records are frozen, never mutated."""
    return CodegraphNode(cell=node.cell, types=node.types, dependencies=node.dependencies, children=children)


def _node_dependencies(source: Path, links: list[CellLink]) -> dict[str, list[str]]:
    """Aggregate the links of one unit into its dependency mapping."""
    types_by_target: dict[str, set[str]] = {}

    for link in links:
        if link.source != source:
            continue

        types_by_target.setdefault(os.path.normpath(link.target), set()).update(link.types)

    return {target: sorted(types) for target, types in sorted(types_by_target.items())}


def _build_forest(units: list[Unit], links: list[CellLink]) -> list[CodegraphNode]:
    """Nest the cell units by path, compressing non-cell ancestors away."""
    cell_units = [unit for unit in units if unit.is_cell]
    cell_dirs = {unit.path for unit in cell_units}
    children_by_parent: dict[Path, list[Unit]] = {}

    roots: list[Unit] = []

    for unit in sorted(cell_units, key=lambda item: os.path.normpath(item.path)):
        parent = next((ancestor for ancestor in unit.path.parents if ancestor in cell_dirs), None)

        if parent is None:
            roots.append(unit)
        else:
            children_by_parent.setdefault(parent, []).append(unit)

    def _node(unit: Unit) -> CodegraphNode:
        children = [_node(child) for child in children_by_parent.get(unit.path, [])]

        return CodegraphNode(
            cell=os.path.normpath(unit.path),
            types=unit.facade,
            dependencies=_node_dependencies(unit.path, links),
            children=children,
        )

    return [_node(root) for root in roots]


def _node_in_set(node: CodegraphNode, cells: frozenset[str]) -> bool:
    """Check whether ``node`` or any descendant is one of ``cells``."""
    if node.cell in cells:
        return True

    return any(_node_in_set(child, cells) for child in node.children)


def _keep_matching(node: CodegraphNode, cells: frozenset[str]) -> CodegraphNode | None:
    """Keep ``node`` when it matches or leads to a match; rebuild its children."""
    if node.cell not in cells and not any(_node_in_set(child, cells) for child in node.children):
        return None

    children = [kept for child in node.children if (kept := _keep_matching(child, cells)) is not None]

    return _with_children(node, children)


def _filter_cells(roots: list[CodegraphNode], cells: list[str]) -> list[CodegraphNode]:
    """Keep the matching cells plus their ancestor chain — schema parity."""
    if not cells:
        return roots

    normalized = frozenset(os.path.normpath(cell) for cell in cells)
    kept_roots = [_keep_matching(root, normalized) for root in roots]

    return [root for root in kept_roots if root is not None]


def _has_dependency(node: CodegraphNode, dep_paths: frozenset[str]) -> bool:
    """Check whether ``node`` or any descendant depends on ``dep_paths``."""
    if any(target in dep_paths for target in node.dependencies):
        return True

    return any(_has_dependency(child, dep_paths) for child in node.children)


def _prune_by_dependency(node: CodegraphNode, dep_paths: frozenset[str]) -> CodegraphNode:
    """Keep the depending cells plus their ancestor skeleton — schema parity."""
    children = [_prune_by_dependency(child, dep_paths) for child in node.children if _has_dependency(child, dep_paths)]

    return _with_children(node, children)


def _filter_by_depends_on(roots: list[CodegraphNode], depends_on: list[str]) -> list[CodegraphNode]:
    """Keep the cells whose own or descendant dependencies hit the given paths."""
    if not depends_on:
        return roots

    dep_paths = frozenset(os.path.normpath(path) for path in depends_on)

    return [_prune_by_dependency(root, dep_paths) for root in roots if _has_dependency(root, dep_paths)]


def _prune_depth(node: CodegraphNode, max_depth: int, current_depth: int = 0) -> CodegraphNode:
    """Empty the children of every node at depth >= ``max_depth``; root depth 0."""
    if current_depth >= max_depth:
        return _with_children(node, [])

    children = [_prune_depth(child, max_depth, current_depth + 1) for child in node.children]

    return _with_children(node, children)


def render_graph(
    units: list[Unit],
    links: list[CellLink],
    cells: list[str],
    max_depth: int | None,
    depends_on: list[str],
) -> str:
    """Assemble the hierarchical node tree of the units and render it as JSON.

    Args:
        units: All derived units; only cell units carry output nodes,
            non-cell units survive as structural ancestors of nested cells.
        links: All resolved links, aggregated into per-node dependencies —
            target cell path to the sorted unique imported types.
        cells: Cell paths to include in the output; the matching cells plus
            their ancestor chain survive. Empty list includes all cells.
        max_depth: Maximum nesting depth; None means no limit. Nodes at
            depth >= ``max_depth`` lose their children; the root depth is 0.
        depends_on: Keep a cell only when its own or any descendant
            dependencies contain at least one given path; ancestors of kept
            cells stay so the parent-child skeleton remains intact.

    Returns:
        The serialized tree — an empty forest renders as ``[]``; identical
            inputs produce byte-identical output.
    """
    roots = _filter_cells(_build_forest(units, links), cells)
    roots = _filter_by_depends_on(roots, depends_on)

    if max_depth is not None:
        roots = [_prune_depth(root, max_depth) for root in roots]

    if not roots:
        return "[]"

    document = [asdict(root) for root in roots]

    return json.dumps(document, indent=4, sort_keys=True, ensure_ascii=False)
