"""Shared tree-sitter utilities for contract extractors."""

from __future__ import annotations

from .data import EntityContract, RoutineContract


def node_text(node) -> str:
    """Decode a tree-sitter node's text to a UTF-8 string.

    Args:
        node: A tree-sitter node, or None.

    Returns:
        Decoded text of the node, or an empty string when node is None.
    """
    if node is None:
        return ""
    return node.text.decode("utf-8")


def first_child_by_type(node, type_name):
    """Return the first direct child of ``node`` whose type matches ``type_name``.

    Args:
        node: A tree-sitter node to inspect.
        type_name: The tree-sitter node type identifier to match.

    Returns:
        The first matching child node, or None when no match is found.
    """
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def build_signature(params: str, return_type: str = "") -> str:
    """Build a signature string from parameters and an optional return type.

    Args:
        params: Comma-separated parameter list string.
        return_type: Optional return type annotation. Empty string omits it.

    Returns:
        Signature string in ``(params) -> return_type`` form, or ``(params)`` when no return type.
    """
    sig = f"({params})"
    if return_type:
        sig += f" -> {return_type}"
    return sig


def sort_contracts(
    entities: dict[str, EntityContract],
    routines: dict[str, RoutineContract],
) -> list[EntityContract | RoutineContract]:
    """Sort entity internals and return a merged, sorted list of all contracts.

    Args:
        entities: Mapping of entity name to EntityContract.
        routines: Mapping of routine name to RoutineContract.

    Returns:
        Sorted list with entities first, then routines, both ordered by name.
    """
    for entity in entities.values():
        entity.properties.sort(key=lambda p: p.name)
        entity.methods.sort(key=lambda m: m.name)
    sorted_entities = sorted(entities.values(), key=lambda e: e.name)
    sorted_routines = sorted(routines.values(), key=lambda r: r.name)
    return sorted_entities + sorted_routines
