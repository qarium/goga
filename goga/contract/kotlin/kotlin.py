"""Kotlin contract extraction — extracts facade from Kotlin packages via tree-sitter."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_kotlin as tskotlin
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

_KOTLIN_LANG = Language(tskotlin.language())
_PARSER = Parser(_KOTLIN_LANG)


def _extract_identifier(node) -> str:
    """Extract identifier text — supports both 'identifier' and 'simple_identifier' node types."""
    ident = _first_child_by_type(node, "identifier") or _first_child_by_type(node, "simple_identifier")
    return _node_text(ident) if ident else ""


def _extract_type_identifier(node) -> str:
    """Extract type identifier text — supports both 'identifier' and 'type_identifier' node types."""
    ident = _first_child_by_type(node, "identifier") or _first_child_by_type(node, "type_identifier")
    return _node_text(ident) if ident else ""


def _unwrap_statements(root):
    """Unwrap 'statement' wrapper nodes if present (newer tree-sitter-kotlin versions)."""
    children = root.children
    if children and children[0].type == "statement":
        unwrapped = []
        for child in children:
            if child.type == "statement":
                for inner in child.children:
                    unwrapped.append(inner)
            else:
                unwrapped.append(child)
        return unwrapped
    return children


def _is_public(node) -> bool:
    for child in node.children:
        if child.type == "modifiers":
            for mod in child.children:
                if mod.type == "visibility_modifier":
                    text = mod.text.decode("utf-8")
                    return text == "public"
    return True  # Kotlin default = public


def _extract_primary_constructor_signature(node) -> str:
    ctor = _first_child_by_type(node, "primary_constructor")
    if ctor is None:
        return "()"
    # Newer versions wrap params in class_parameters
    class_params = _first_child_by_type(ctor, "class_parameters")
    params_container = class_params if class_params else ctor
    params = _extract_class_params(params_container)
    return f"({params})"


def _extract_class_params(container_node) -> str:
    parts: list[str] = []
    for child in container_node.children:
        if child.type != "class_parameter":
            continue
        name = _extract_identifier(child)
        type_node = (
                _first_child_by_type(child, "user_type")
                or _first_child_by_type(child, "nullable_type")
                or _first_child_by_type(child, "function_type")
        )
        type_str = _node_text(type_node) if type_node else ""
        if name and type_str:
            parts.append(f"{name}: {type_str}")
        elif name:
            parts.append(name)
    return ", ".join(parts)


def _extract_kotlin_params(node) -> str:
    fvp = _first_child_by_type(node, "function_value_parameters")
    if fvp is None:
        return ""
    parts: list[str] = []
    for child in fvp.children:
        if child.type != "parameter":
            continue
        name = _extract_identifier(child)
        type_node = (
                _first_child_by_type(child, "user_type")
                or _first_child_by_type(child, "nullable_type")
                or _first_child_by_type(child, "function_type")
        )
        type_str = _node_text(type_node) if type_node else ""
        if name and type_str:
            parts.append(f"{name}: {type_str}")
        elif name:
            parts.append(name)
    return ", ".join(parts)


def _extract_return_type(func_node) -> str:
    found_fvp = False
    for child in func_node.children:
        if child.type == "function_value_parameters":
            found_fvp = True
            continue
        if found_fvp and child.type in ("user_type", "nullable_type", "function_type"):
            return child.text.decode("utf-8")
    return ""


def _extract_class_properties(body_node) -> list[PropertyContract]:
    properties: list[PropertyContract] = []
    for child in body_node.children:
        if child.type != "property_declaration":
            continue
        if not _is_public(child):
            continue
        var_decl = _first_child_by_type(child, "variable_declaration")
        if var_decl is None:
            continue
        name = _extract_identifier(var_decl)
        if not name:
            continue
        type_node = (
                _first_child_by_type(var_decl, "user_type")
                or _first_child_by_type(var_decl, "nullable_type")
                or _first_child_by_type(var_decl, "function_type")
        )
        type_str = _node_text(type_node) if type_node else ""
        properties.append(PropertyContract(name=name, signature=type_str))
    return properties


def _extract_class_methods(body_node) -> list[MethodContract]:
    methods: list[MethodContract] = []
    for child in body_node.children:
        if child.type == "companion_object":
            continue
        if child.type != "function_declaration":
            continue
        if not _is_public(child):
            continue
        name = _extract_identifier(child)
        if not name:
            continue
        params = _extract_kotlin_params(child)
        ret = _extract_return_type(child)
        sig = f"({params})"
        if ret:
            sig += f" -> {ret}"
        methods.append(MethodContract(name=name, signature=sig))
    return methods


def _process_class_declaration(node, entities: dict[str, EntityContract]) -> None:
    name = _extract_type_identifier(node)
    if not name:
        return
    if not _is_public(node):
        return
    signature = _extract_primary_constructor_signature(node)
    body = _first_child_by_type(node, "class_body")
    if body is None:
        body = _first_child_by_type(node, "enum_class_body")
    methods: list[MethodContract] = []
    properties: list[PropertyContract] = []
    if body:
        methods = _extract_class_methods(body)
        properties = _extract_class_properties(body)
    entities[name] = EntityContract(name=name, signature=signature, properties=properties, methods=methods)


def _process_object_declaration(node, entities: dict[str, EntityContract]) -> None:
    name = _extract_type_identifier(node)
    if not name:
        return
    if not _is_public(node):
        return
    body = _first_child_by_type(node, "class_body")
    methods: list[MethodContract] = []
    properties: list[PropertyContract] = []
    if body:
        methods = _extract_class_methods(body)
        properties = _extract_class_properties(body)
    entities[name] = EntityContract(name=name, signature="()", properties=properties, methods=methods)


def _is_extension_function(func_node) -> bool:
    """Detect extension functions by checking for user_type/nullable_type + '.' pattern."""
    children = func_node.children
    for i, child in enumerate(children):
        if child.type in ("user_type", "nullable_type") and i + 1 < len(children) and children[i + 1].type == ".":
            return True
    return False


def _extract_receiver_type_name(func_node) -> str:
    """Extract the receiver type name from an extension function declaration."""
    children = func_node.children
    for i, child in enumerate(children):
        if child.type == "user_type" and i + 1 < len(children) and children[i + 1].type == ".":
            ident = _first_child_by_type(child, "identifier") or _first_child_by_type(child, "type_identifier")
            return _node_text(ident) if ident else ""
        if child.type == "nullable_type" and i + 1 < len(children) and children[i + 1].type == ".":
            ut = _first_child_by_type(child, "user_type")
            if ut:
                ident = _first_child_by_type(ut, "identifier") or _first_child_by_type(ut, "type_identifier")
                return _node_text(ident) if ident else ""
    return ""


def _process_extension_function(node, methods_by_receiver: dict[str, list[MethodContract]]) -> None:
    receiver_type_name = _extract_receiver_type_name(node)
    if not receiver_type_name:
        return
    if not _is_public(node):
        return
    name = _extract_identifier(node)
    if not name:
        return
    params = _extract_kotlin_params(node)
    ret = _extract_return_type(node)
    sig = f"({params})"
    if ret:
        sig += f" -> {ret}"
    methods_by_receiver.setdefault(receiver_type_name, []).append(MethodContract(name=name, signature=sig))


def _process_top_level_function(node, routines: dict[str, RoutineContract]) -> None:
    if not _is_public(node):
        return
    name = _extract_identifier(node)
    if not name:
        return
    params = _extract_kotlin_params(node)
    ret = _extract_return_type(node)
    sig = f"({params})"
    if ret:
        sig += f" -> {ret}"
    routines[name] = RoutineContract(name=name, signature=sig)


def _collect_contracts(
        kt_files: list[Path],
) -> tuple[
    dict[str, EntityContract],
    dict[str, RoutineContract],
    dict[str, list[MethodContract]],
]:
    entities: dict[str, EntityContract] = {}
    routines: dict[str, RoutineContract] = {}
    methods_by_receiver: dict[str, list[MethodContract]] = {}

    for kt_file in kt_files:
        source = kt_file.read_bytes()
        tree = _PARSER.parse(source)
        root = tree.root_node

        for node in _unwrap_statements(root):
            if node.type == "class_declaration":
                _process_class_declaration(node, entities)
            elif node.type == "object_declaration":
                _process_object_declaration(node, entities)
            elif node.type == "function_declaration":
                if _is_extension_function(node):
                    _process_extension_function(node, methods_by_receiver)
                else:
                    _process_top_level_function(node, routines)

    return entities, routines, methods_by_receiver


def kotlin_contract(cell_path: str) -> list[EntityContract | RoutineContract]:
    """Extract the contract (facade) from a Kotlin package via tree-sitter.

    Args:
        cell_path: Path to the Kotlin package directory.

    Returns:
        Sorted list of EntityContract and RoutineContract instances.
    """
    pkg_dir = Path(cell_path)
    kt_files = sorted(pkg_dir.glob("*.kt"))

    if not kt_files:
        return []

    entities, routines, methods_by_receiver = _collect_contracts(kt_files)

    # Attach extension functions to their receiver entities
    for receiver_type, methods in methods_by_receiver.items():
        if receiver_type in entities:
            entities[receiver_type].methods.extend(methods)

    return sort_contracts(entities, routines)
