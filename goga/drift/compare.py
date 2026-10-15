"""Comparison core — the drift entries of the two complete views and their scoping.

The module owns the flat report record and the two pure steps over the view
trees: the name-level comparison of the complete views and the survival
scoping over the filtered views. No filters are applied here — the entries
are facts of the views passed in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..codegraph.facts import CodegraphNode
from ..schema.hooks import SchemaNode

SCHEMA_ONLY = "schema_only"
CODEGRAPH_ONLY = "codegraph_only"


@dataclass(frozen=True, kw_only=True)
class DriftEntry:
    """One flat entry of the drift report.

    Args:
        kind: Direction of the discrepancy — ``schema_only`` or
            ``codegraph_only``.
        cell: Normalized cell path of the discrepancy subject.
        types: Sorted type names of the cell missing from the other view;
            ``None`` marks a cell-level discrepancy.
        tools: The committed tools overlay of the entry; empty when no
            tool contributed — the entry-facts amendment alone places
            non-empty overlays.
    """

    kind: str
    cell: str
    types: list[str] | None = None
    tools: dict[str, dict[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Copy the caller-owned type list into a fresh list."""
        if self.types is not None:
            object.__setattr__(self, "types", list(self.types))


def _index_schema(nodes: list[SchemaNode]) -> dict[str, set[str]]:
    """Walk the schema tree recursively and index cell paths to their type-name sets.

    Args:
        nodes: One level of the declared view tree.

    Returns:
        Every cell path of the subtree mapped to its set of type names.
    """
    index: dict[str, set[str]] = {}

    for node in nodes:
        index[node.path] = set(node.types)
        index.update(_index_schema(node.children))

    return index


def _index_codegraph(nodes: list[CodegraphNode]) -> dict[str, set[str]]:
    """Walk the codegraph tree recursively and index cell paths to their type-name sets.

    Args:
        nodes: One level of the code-derived view tree.

    Returns:
        Every cell path of the subtree mapped to its set of type names.
    """
    index: dict[str, set[str]] = {}

    for node in nodes:
        index[node.cell] = set(node.types)
        index.update(_index_codegraph(node.children))

    return index


def compare_views(
    schema_tree: list[SchemaNode],
    codegraph_tree: list[CodegraphNode],
) -> list[DriftEntry]:
    """Compare the two complete views and produce every structural discrepancy entry.

    Args:
        schema_tree: The complete declared view of the project.
        codegraph_tree: The complete code-derived view of the project.

    Returns:
        Every discrepancy of the two views — one cell-level entry per path
        present in exactly one view, one type-level entry per direction of
        every shared path with missing type names, ordered by cell path then
        kind.
    """
    schema_index = _index_schema(schema_tree)
    codegraph_index = _index_codegraph(codegraph_tree)
    entries: list[DriftEntry] = []

    for path in schema_index.keys() - codegraph_index.keys():
        entries.append(DriftEntry(kind=SCHEMA_ONLY, cell=path, types=None))

    for path in codegraph_index.keys() - schema_index.keys():
        entries.append(DriftEntry(kind=CODEGRAPH_ONLY, cell=path, types=None))

    for path in schema_index.keys() & codegraph_index.keys():
        declared_only = sorted(schema_index[path] - codegraph_index[path])
        code_only = sorted(codegraph_index[path] - schema_index[path])

        if declared_only:
            entries.append(DriftEntry(kind=SCHEMA_ONLY, cell=path, types=declared_only))

        if code_only:
            entries.append(DriftEntry(kind=CODEGRAPH_ONLY, cell=path, types=code_only))

    entries.sort(key=lambda entry: (entry.cell, entry.kind))

    return entries


def scope_entries(
    entries: list[DriftEntry],
    schema_tree: list[SchemaNode],
    codegraph_tree: list[CodegraphNode],
) -> list[DriftEntry]:
    """Scope the computed entries to the filtered views.

    Args:
        entries: The computed discrepancies of the complete views.
        schema_tree: The filtered declared view of the project.
        codegraph_tree: The filtered code-derived view of the project.

    Returns:
        The surviving entries — an entry survives iff its cell survives in
        at least one of the two filtered views; the input order is preserved.
    """
    surviving = _index_schema(schema_tree).keys() | _index_codegraph(codegraph_tree).keys()

    return [entry for entry in entries if entry.cell in surviving]
