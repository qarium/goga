from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import click
import yaml

from ...ast import AST
from ...ast.errors import DocumentNotFoundError
from ...config import load_project_config
from ...contract import (
    EntityContract,
    MethodContract,
    PropertyContract,
    RoutineContract,
)
from ...contract import (
    contract as contract_logic,
)

if TYPE_CHECKING:
    from ...ast.nodes import EntityTypeNode, MethodNode, PropertyNode, RoutineTypeNode


def _compare_property(
    prop_node: PropertyNode,
    impl_props: dict[str, PropertyContract],
) -> dict:
    """Build a codemanifest/implementation comparison for a single property.

    Args:
        prop_node: The property definition declared in the CODEMANIFEST.
        impl_props: Implementation-side properties keyed by name.

    Returns:
        A dict with `codemanifest` and `implementation` signature entries.
    """
    impl = impl_props[prop_node.name].signature if prop_node.name in impl_props else None
    return {"codemanifest": prop_node.type, "implementation": impl}


def _compare_method(
    method_node: MethodNode,
    impl_methods: dict[str, MethodContract],
) -> dict:
    """Build a codemanifest/implementation comparison for a single method.

    Args:
        method_node: The method definition declared in the CODEMANIFEST.
        impl_methods: Implementation-side methods keyed by name.

    Returns:
        A dict with `codemanifest` and `implementation` signature entries.
    """
    impl = impl_methods[method_node.name].signature if method_node.name in impl_methods else None
    return {"codemanifest": method_node.signature, "implementation": impl}


def _match_entity(
    entity_node: EntityTypeNode,
    impl_entity: EntityContract | None,
) -> dict:
    """Build the full comparison structure for one entity.

    Args:
        entity_node: The entity definition declared in the CODEMANIFEST.
        impl_entity: Matching implementation entity contract, or None when the
            entity has no implementation.

    Returns:
        A dict carrying signature, property, and method comparisons.
    """
    result: dict = {
        "signature": {
            "codemanifest": entity_node.signature,
            "implementation": impl_entity.signature if impl_entity else None,
        },
        "properties": {},
        "methods": {},
    }
    impl_props = {p.name: p for p in impl_entity.properties} if impl_entity else {}

    for prop in entity_node.properties:
        result["properties"][prop.name] = _compare_property(prop, impl_props)

    impl_methods = {m.name: m for m in impl_entity.methods} if impl_entity else {}

    for method in entity_node.methods:
        result["methods"][method.name] = _compare_method(method, impl_methods)

    return result


def _build_cell_compare(
    entities: list[EntityTypeNode],
    routines: list[RoutineTypeNode],
    impl_contracts: list[EntityContract | RoutineContract],
) -> dict:
    """Build the comparison structure for all entities and routines in a cell.

    Args:
        entities: Entity definitions declared in the CODEMANIFEST body.
        routines: Routine definitions declared in the CODEMANIFEST body.
        impl_contracts: Implementation-side contracts matched by name.

    Returns:
        A dict keyed by entity/routine name carrying their comparisons.
    """
    impl_by_name: dict[str, EntityContract | RoutineContract] = {c.name: c for c in impl_contracts}
    result: dict = {}

    for entity in entities:
        impl = impl_by_name.get(entity.name)
        if not isinstance(impl, EntityContract):
            impl = None

        result[entity.name] = _match_entity(entity, impl)

    for routine in routines:
        impl = impl_by_name.get(routine.name)
        if not isinstance(impl, RoutineContract):
            impl = None

        result[routine.name] = {
            "signature": {
                "codemanifest": routine.signature,
                "implementation": impl.signature if impl else None,
            }
        }

    return result


@click.command()
@click.argument("cells", nargs=-1)
@click.option("--lang", default=None)
@click.pass_context
def contract(ctx: click.Context, cells: tuple[str, ...], lang: str | None) -> None:
    """Compare CODEMANIFEST contract with implementation.

    For each specified cell, loads the CODEMANIFEST definitions and the
    implementation, then outputs a JSON object with codemanifest/implementation
    pairs for every signature, property, and method.

    \b
    JSON output per cell:
      <cell_path>          - normalized cell path as key
        <EntityName>       - entity with:
          signature        - {codemanifest, implementation} pair
          properties       - dict of {name: {codemanifest, implementation}}
          methods          - dict of {name: {codemanifest, implementation}}
        <RoutineName>      - routine with:
          signature        - {codemanifest, implementation} pair
    """
    try:
        config = load_project_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    lang = lang if lang is not None else config.lang

    ast_obj = AST(".")
    ast_obj.load()

    result: dict = {}

    for cell_path in cells:
        try:
            doc = ast_obj.document(cell_path)
        except DocumentNotFoundError:
            click.echo(f"Error: document not found: {cell_path}", err=True)
            ctx.exit(1)

        try:
            impl_contracts = contract_logic(lang, cell_path)
        except ModuleNotFoundError:
            click.echo(f"Error: package not importable: {cell_path}", err=True)
            ctx.exit(1)
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
            ctx.exit(1)

        compare = _build_cell_compare(doc.body.entities, doc.body.routines, impl_contracts)
        result[os.path.normpath(doc.path)] = compare

    json_str = json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
    click.echo(json_str)
