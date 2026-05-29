"""Python contract extraction — extracts public definitions from Python packages via tree-sitter."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from ..data import EntityContract, MethodContract, PropertyContract, RoutineContract
from ..treesitter_utils import build_signature, sort_contracts
from ..treesitter_utils import node_text as _node_text

_PY_LANG = Language(tspython.language())
_PARSER = Parser(_PY_LANG)

_SKIP_TYPES = frozenset({"(", ")", ",", "comment"})
_SPLAT_LIST = frozenset({"list_parameter_pattern", "list_splat_pattern"})
_SPLAT_DICT = frozenset({"dictionary_parameter_pattern", "dictionary_splat_pattern"})


def _first_identifier(node) -> str:
    for c in node.children:
        if c.type == "identifier":
            return _node_text(c)
    return ""


def _handle_typed_parameter(child) -> str | None:
    type_node = child.child_by_field_name("type")
    name = _first_identifier(child)
    if name == "self":
        return None
    return f"{name}: {_node_text(type_node)}"


def _handle_default_parameter(child) -> str | None:
    name_node = child.child_by_field_name("name")
    value_node = child.child_by_field_name("value")
    name = _node_text(name_node)
    if name == "self":
        return None
    return f"{name}={_node_text(value_node)}"


def _handle_identifier(child) -> str | None:
    name = _node_text(child)
    return None if name == "self" else name


def _handle_typed_default(child) -> str | None:
    name_node = child.child_by_field_name("name")
    type_node = child.child_by_field_name("type")
    value_node = child.child_by_field_name("value")
    name = _node_text(name_node)
    if name == "self":
        return None
    return f"{name}: {_node_text(type_node)} = {_node_text(value_node)}"


_PARAM_HANDLERS = {
    "identifier": _handle_identifier,
    "typed_parameter": _handle_typed_parameter,
    "default_parameter": _handle_default_parameter,
    "typed_default_parameter": _handle_typed_default,
}


def _extract_params(params_node) -> str:
    if params_node is None:
        return ""
    parts: list[str] = []
    for child in params_node.children:
        if child.type in _SKIP_TYPES:
            continue
        handler = _PARAM_HANDLERS.get(child.type)
        if handler:
            part = handler(child)
            if part:
                parts.append(part)
        elif child.type in _SPLAT_LIST:
            parts.append(f"*{_first_identifier(child)}")
        elif child.type in _SPLAT_DICT:
            parts.append(f"**{_first_identifier(child)}")
    return ", ".join(parts)


def _extract_return_type(node) -> str:
    rt = node.child_by_field_name("return_type")
    return _node_text(rt) if rt else ""


def _is_property_decorator(decorator_node) -> bool:
    return any(
        child.type == "identifier" and _node_text(child) == "property"
        for child in decorator_node.children
    )


def _func_name(func_node) -> str:
    name_node = func_node.child_by_field_name("name")
    return _node_text(name_node) if name_node else ""


def _make_method(func_node) -> MethodContract:
    params = _extract_params(func_node.child_by_field_name("parameters"))
    ret = _extract_return_type(func_node)
    return MethodContract(name=_func_name(func_node), signature=build_signature(params, ret))


def _try_extract_annotated_field(child, properties) -> None:
    """Extract type-annotated class fields (PEP 526) as properties."""
    if child.type != "expression_statement":
        return
    assign = child.children[0] if child.children else None
    if assign is None or assign.type != "assignment":
        return
    type_node = assign.child_by_field_name("type")
    if type_node is None:
        return
    ident = next((c for c in assign.children if c.type == "identifier"), None)
    if ident is None:
        return
    field_name = _node_text(ident)
    if not field_name.startswith("_"):
        properties.append(PropertyContract(name=field_name, signature=_node_text(type_node)))


def _process_class_member(child, properties, methods) -> str:  # noqa: C901
    """Process a single body child. Returns init_signature if __init__ found, else None."""
    if child.type == "function_definition":
        name = _func_name(child)
        if name == "__init__":
            params = _extract_params(child.child_by_field_name("parameters"))
            return f"({params})"
        if not name.startswith("_"):
            methods.append(_make_method(child))
        return ""

    _try_extract_annotated_field(child, properties)
    if child.type != "decorated_definition":
        return ""

    is_property = False
    func_def = None
    for dc in child.children:
        if dc.type == "decorator":
            is_property = _is_property_decorator(dc)
        elif dc.type in ("function_definition", "class_definition"):
            func_def = dc

    if func_def is None:
        return ""

    name = _func_name(func_def)
    if name.startswith("_"):
        return ""

    if is_property:
        properties.append(PropertyContract(name=name, signature=_extract_return_type(func_def)))
    else:
        methods.append(_make_method(func_def))
    return ""


def _extract_entity(class_node, name: str) -> EntityContract:
    body = class_node.child_by_field_name("body")
    properties: list[PropertyContract] = []
    methods: list[MethodContract] = []
    init_signature = "()"

    if body is not None:
        for child in body.children:
            result = _process_class_member(child, properties, methods)
            if result:
                init_signature = result

    return EntityContract(
        name=name,
        signature=init_signature,
        properties=properties,
        methods=methods,
    )


def _extract_routine(func_node, name: str) -> RoutineContract:
    params = _extract_params(func_node.child_by_field_name("parameters"))
    ret = _extract_return_type(func_node)
    return RoutineContract(name=name, signature=build_signature(params, ret))


def _collect_definitions(tree, definitions: dict[str, tuple[str, object]]) -> None:
    for node in tree.root_node.children:
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                definitions[_node_text(name_node)] = ("class", node)
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                definitions[_node_text(name_node)] = ("function", node)
        elif node.type == "decorated_definition":
            for inner in node.children:
                if inner.type in ("class_definition", "function_definition"):
                    name_node = inner.child_by_field_name("name")
                    if name_node:
                        kind = "class" if inner.type == "class_definition" else "function"
                        definitions[_node_text(name_node)] = (kind, inner)


def python_contract(cell_path: str) -> list[EntityContract | RoutineContract]:
    """Extract public definitions from a Python package via tree-sitter.

    Args:
        cell_path: Path to the package in ``path/to/cell`` format.

    Returns:
        Sorted list of EntityContract and RoutineContract instances for all public definitions.
    """
    pkg_dir = Path(cell_path)
    if not pkg_dir.is_dir():
        raise FileNotFoundError(cell_path)

    py_files = sorted(pkg_dir.glob("*.py"))
    if not py_files:
        return []

    definitions: dict[str, tuple[str, object]] = {}
    for py_file in py_files:
        source = py_file.read_bytes()
        tree = _PARSER.parse(source)
        _collect_definitions(tree, definitions)

    entities: dict[str, EntityContract] = {}
    routines: dict[str, RoutineContract] = {}
    for name, (kind, node) in definitions.items():
        if name.startswith("_"):
            continue
        if kind == "class":
            entities[name] = _extract_entity(node, name)
        elif kind == "function":
            routines[name] = _extract_routine(node, name)

    return sort_contracts(entities, routines)
