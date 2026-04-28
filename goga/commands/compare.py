from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import click

from ..ast import AST
from ..ast.errors import DocumentNotFoundError
from ..contract import EntityContract, MethodContract, PropertyContract, RoutineContract
from ..contract.python import python_contract

if TYPE_CHECKING:
    from ..ast.nodes import EntityTypeNode, MethodNode, PropertyNode, RoutineTypeNode


def _compare_property(
    prop_node: PropertyNode,
    impl_props: dict[str, PropertyContract],
) -> dict:
    impl = impl_props[prop_node.name].signature if prop_node.name in impl_props else None
    return {"codemanifest": prop_node.type, "implementation": impl}


def _compare_method(
    method_node: MethodNode,
    impl_methods: dict[str, MethodContract],
) -> dict:
    impl = impl_methods[method_node.name].signature if method_node.name in impl_methods else None
    return {"codemanifest": method_node.signature, "implementation": impl}


def _match_entity(
    entity_node: EntityTypeNode,
    impl_entity: EntityContract | None,
) -> dict:
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
@click.option("--lang", default="python")
@click.pass_context
def compare(ctx: click.Context, cells: tuple[str, ...], lang: str) -> None:
    """Compare CODEMANIFEST contract with implementation.

    For each specified cell, loads the CODEMANIFEST definitions and
    the Python implementation, then outputs a JSON object with
    codemanifest/implementation pairs for every signature, property,
    and method.

    \b
    JSON output per cell:
      <cell_path>          - normalized cell path as key
        <EntityName>       - entity with:
          signature        - {codemanifest, implementation} pair
          properties       - dict of {name: {codemanifest, implementation}}
          methods          - dict of {name: {codemanifest, implementation}}
        <RoutineName>      - routine with:
          signature        - {codemanifest, implementation} pair

    \b
    Options:
      cells          - one or more cell paths to compare (variadic)
      --lang         - implementation language (default: python)

    Exit codes: 0 on success, 1 on error (cell not found, package not importable).
    """
    _ = lang  # reserved for future use
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
            impl_contracts = python_contract(cell_path)
        except ModuleNotFoundError:
            click.echo(f"Error: package not importable: {cell_path}", err=True)
            ctx.exit(1)
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
            ctx.exit(1)

        result[os.path.normpath(doc.path)] = _build_cell_compare(
            doc.body.entities, doc.body.routines, impl_contracts
        )

    json_str = json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
    click.echo(json_str)
