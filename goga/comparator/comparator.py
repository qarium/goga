"""Compare CODEMANIFEST contracts with Python source implementation."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ..contract import python_contract
from ..contract.contract import EntityContract, RoutineContract

if TYPE_CHECKING:
    from goga.ast.nodes import DocumentRoot
    from goga.ast.nodes.body import EntityTypeNode


def _build_flat_lookup(tree: list[DocumentRoot]) -> dict[str, DocumentRoot]:
    lookup: dict[str, DocumentRoot] = {}
    for doc in tree:
        lookup[os.path.normpath(doc.path)] = doc
        lookup.update(_build_flat_lookup(doc.children))
    return lookup


def _resolve_mutations(
    entity: EntityTypeNode,
    lookup: dict[str, DocumentRoot],
    visited: set[int] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    if visited is None:
        visited = set()
    entity_id = id(entity)
    if entity_id in visited:
        return {}, {}
    visited = visited | {entity_id}

    methods: dict[str, str] = {}
    properties: dict[str, str] = {}

    for base_name, base_doc_path in entity.mutations:
        norm_path = os.path.normpath(base_doc_path)
        base_doc = lookup.get(norm_path)
        if base_doc is None:
            continue
        base_entity = None
        for e in base_doc.body.entities:
            if e.name == base_name or e.name.split("::")[-1] == base_name:
                base_entity = e
                break
        if base_entity is None:
            continue
        base_methods, base_props = _resolve_mutations(base_entity, lookup, visited)
        methods.update(base_methods)
        properties.update(base_props)
        for m in base_entity.methods:
            methods[m.name] = m.signature
        for p in base_entity.properties:
            properties[p.name] = p.type

    return methods, properties


def _extract_manifest(
    doc: DocumentRoot,
    lookup: dict[str, DocumentRoot],
) -> dict:
    manifest: dict = {}

    for entity in doc.body.entities:
        final_name = entity.name.split("::")[-1]
        base_methods, base_props = _resolve_mutations(entity, lookup)
        methods: dict[str, str] = dict(base_methods)
        properties: dict[str, str] = dict(base_props)
        for m in entity.methods:
            methods[m.name] = m.signature
        for p in entity.properties:
            properties[p.name] = p.type
        manifest[final_name] = {
            "()": entity.signature,
            "methods": methods,
            "properties": properties,
        }

    for routine in doc.body.routines:
        manifest[routine.name] = routine.signature

    return manifest


def _extract_source(doc: DocumentRoot) -> dict:
    try:
        contracts = python_contract(doc.path)
    except (ImportError, ValueError):
        return {}

    source: dict = {}
    for contract in contracts:
        if isinstance(contract, EntityContract):
            source[contract.name] = {
                "()": contract.signature,
                "methods": {m.name: m.signature for m in contract.methods},
                "properties": {p.name: p.signature for p in contract.properties},
            }
        elif isinstance(contract, RoutineContract):
            source[contract.name] = contract.signature
    return source


def compare(tree: list[DocumentRoot], paths: list[str] | None = None) -> dict:
    lookup = _build_flat_lookup(tree)

    norm_paths = {os.path.normpath(p) for p in paths} if paths else None

    result: dict = {}
    for doc in lookup.values():
        doc_norm = os.path.normpath(doc.path)
        if norm_paths is not None and doc_norm not in norm_paths:
            continue
        result[doc.path] = {
            "codemanifest": _extract_manifest(doc, lookup),
            "source": _extract_source(doc),
        }

    return result
