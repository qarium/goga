"""Swift contract extraction — extracts facade from Swift packages via tree-sitter."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_swift as tsswift
from tree_sitter import Language, Parser

from ..data import EntityContract, MethodContract, PropertyContract, RoutineContract
from ..treesitter_utils import (
    first_child_by_type as _first_child_by_type,
)
from ..treesitter_utils import (
    node_text as _node_text,
)
from ..treesitter_utils import (
    sort_contracts,
)

_SWIFT_LANG = Language(tsswift.language())
_PARSER = Parser(_SWIFT_LANG)


def _is_swift_public(node) -> bool:
    for child in node.children:
        if child.type == "modifiers":
            for mod in child.children:
                if mod.type == "visibility_modifier":
                    text = mod.text.decode("utf-8")
                    return text in ("public", "open")
    return False  # Swift default = internal -> NOT in contract


def _extract_swift_func_params(func_node) -> str:
    parts: list[str] = []
    for child in func_node.children:
        if child.type != "parameter":
            continue
        ext_name = child.child_by_field_name("external_name")
        name = child.child_by_field_name("name")
        type_node = child.child_by_field_name("type")
        ext_str = _node_text(ext_name) if ext_name else ""
        name_str = _node_text(name) if name else ""
        type_str = _node_text(type_node) if type_node else ""
        if ext_str and ext_str != name_str:
            parts.append(f"{ext_str} {name_str}: {type_str}")
        elif name_str:
            parts.append(f"{name_str}: {type_str}")
    return ", ".join(parts)


def _extract_swift_init_params(init_node) -> str:
    params = _extract_swift_func_params(init_node)
    return f"({params})"


def _extract_swift_class_methods(body_node) -> list[MethodContract]:
    methods: list[MethodContract] = []
    for child in body_node.children:
        if child.type != "function_declaration":
            continue
        if not _is_swift_public(child):
            continue
        name_node = child.child_by_field_name("name")
        name = _node_text(name_node) if name_node else ""
        if not name:
            continue
        params = _extract_swift_func_params(child)
        return_type_node = child.child_by_field_name("return_type")
        ret = _node_text(return_type_node)
        sig = f"({params})"
        if ret:
            sig += f" -> {ret}"
        methods.append(MethodContract(name=name, signature=sig))
    return methods


def _extract_swift_class_properties(body_node) -> list[PropertyContract]:
    properties: list[PropertyContract] = []
    for child in body_node.children:
        if child.type != "property_declaration":
            continue
        if not _is_swift_public(child):
            continue
        name_node = child.child_by_field_name("name")
        if name_node is None:
            continue
        # name is a "pattern" node; extract bound_identifier
        bound = name_node.child_by_field_name("bound_identifier")
        name = _node_text(bound) if bound else _node_text(name_node)
        if not name:
            continue
        type_annot = _first_child_by_type(child, "type_annotation")
        type_str = ""
        if type_annot:
            type_node = type_annot.child_by_field_name("type")
            type_str = _node_text(type_node)
        properties.append(PropertyContract(name=name, signature=type_str))
    return properties


def _process_swift_class(node, entities: dict[str, EntityContract]) -> None:
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) if name_node else ""
    if not name:
        return
    if not _is_swift_public(node):
        return
    body = node.child_by_field_name("body")
    signature = "()"
    if body:
        for child in body.children:
            if child.type == "init_declaration" and _is_swift_public(child):
                signature = _extract_swift_init_params(child)
                break
    methods: list[MethodContract] = []
    properties: list[PropertyContract] = []
    if body:
        methods = _extract_swift_class_methods(body)
        properties = _extract_swift_class_properties(body)
    entities[name] = EntityContract(name=name, signature=signature, properties=properties, methods=methods)


def _process_swift_enum(node, entities: dict[str, EntityContract]) -> None:
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) if name_node else ""
    if not name:
        return
    if not _is_swift_public(node):
        return
    body = node.child_by_field_name("body")
    properties: list[PropertyContract] = []
    if body:
        for child in body.children:
            if child.type == "enum_entry":
                entry_name_node = child.child_by_field_name("name")
                entry_name = _node_text(entry_name_node) if entry_name_node else ""
                if entry_name:
                    properties.append(PropertyContract(name=entry_name, signature=""))
    entities[name] = EntityContract(name=name, signature="()", properties=properties, methods=[])


def _process_swift_protocol(node, entities: dict[str, EntityContract]) -> None:
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) if name_node else ""
    if not name:
        return
    if not _is_swift_public(node):
        return
    body = node.child_by_field_name("body")
    methods: list[MethodContract] = []
    if body:
        for child in body.children:
            if child.type == "protocol_function_declaration":
                method = _parse_swift_function_as_method(child)
                if method is not None:
                    methods.append(method)
    entities[name] = EntityContract(name=name, signature="()", properties=[], methods=methods)


def _parse_swift_function_as_method(proto_func_node):
    name_node = proto_func_node.child_by_field_name("name")
    name = _node_text(name_node) if name_node else ""
    if not name:
        return None
    params = _extract_swift_func_params(proto_func_node)
    return_type_node = proto_func_node.child_by_field_name("return_type")
    ret = _node_text(return_type_node)
    sig = f"({params})"
    if ret:
        sig += f" -> {ret}"
    return MethodContract(name=name, signature=sig)


def _process_swift_function(node, routines: dict[str, RoutineContract]) -> None:
    if not _is_swift_public(node):
        return
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) if name_node else ""
    if not name:
        return
    params = _extract_swift_func_params(node)
    return_type_node = node.child_by_field_name("return_type")
    ret = _node_text(return_type_node)
    sig = f"({params})"
    if ret:
        sig += f" -> {ret}"
    routines[name] = RoutineContract(name=name, signature=sig)


def _collect_contracts(
        swift_files: list[Path],
) -> tuple[dict[str, EntityContract], dict[str, RoutineContract]]:
    entities: dict[str, EntityContract] = {}
    routines: dict[str, RoutineContract] = {}

    for swift_file in swift_files:
        source = swift_file.read_bytes()
        tree = _PARSER.parse(source)
        root = tree.root_node

        for node in root.children:
            if node.type == "class_declaration":
                kind = node.child_by_field_name("declaration_kind")
                kind_str = _node_text(kind) if kind else "class"
                if kind_str in ("class", "struct", "actor"):
                    _process_swift_class(node, entities)
                elif kind_str == "enum":
                    _process_swift_enum(node, entities)
                # extension -> skip
            elif node.type == "protocol_declaration":
                _process_swift_protocol(node, entities)
            elif node.type == "function_declaration":
                _process_swift_function(node, routines)

    return entities, routines


def swift_contract(cell_path: str) -> list[EntityContract | RoutineContract]:
    """Extract the contract (facade) from a Swift package via tree-sitter.

    Args:
        cell_path: Path to the Swift package directory.

    Returns:
        Sorted list of EntityContract and RoutineContract instances.
    """
    pkg_dir = Path(cell_path)
    swift_files = sorted(pkg_dir.glob("*.swift"))

    if not swift_files:
        return []

    entities, routines = _collect_contracts(swift_files)

    return sort_contracts(entities, routines)
