"""Shared tree-sitter utilities for contract extractors."""

from __future__ import annotations

from .data import EntityContract, RoutineContract


def node_text(node) -> str:
    """Decode a tree-sitter node's text to a UTF-8 string. Returns '' for None."""
    if node is None:
        return ""
    return node.text.decode("utf-8")


def first_child_by_type(node, type_name):
    """Return the first direct child of `node` whose type matches `type_name`, or None."""
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def build_signature(params: str, return_type: str = "") -> str:
    """Build a signature string from parameters and optional return type."""
    sig = f"({params})"
    if return_type:
        sig += f" -> {return_type}"
    return sig


def sort_contracts(
    entities: dict[str, EntityContract],
    routines: dict[str, RoutineContract],
) -> list[EntityContract | RoutineContract]:
    """Sort entity internals and return a merged, sorted list of all contracts."""
    for entity in entities.values():
        entity.properties.sort(key=lambda p: p.name)
        entity.methods.sort(key=lambda m: m.name)
    sorted_entities = sorted(entities.values(), key=lambda e: e.name)
    sorted_routines = sorted(routines.values(), key=lambda r: r.name)
    return sorted_entities + sorted_routines
