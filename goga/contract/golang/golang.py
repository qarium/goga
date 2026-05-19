"""Go contract extraction — extracts facade from Go packages via tree-sitter."""

from pathlib import Path

import tree_sitter_go as tsgo
from tree_sitter import Language, Parser

from ..data import EntityContract, MethodContract, PropertyContract, RoutineContract

GO_LANG = Language(tsgo.language())
_PARSER = Parser(GO_LANG)


def _is_exported(name: str) -> bool:
    return bool(name) and name[0].isupper()


def _node_text(node) -> str:
    if node is None:
        return ""
    return node.text.decode("utf-8")


def _extract_params(param_list_node) -> str:
    if param_list_node is None:
        return ""
    parts: list[str] = []
    param_types = ("parameter_declaration", "variadic_parameter_declaration")
    children = [c for c in param_list_node.children if c.type in param_types]
    for param in children:
        type_node = param.child_by_field_name("type")
        if type_node is None:
            continue
        type_text = _node_text(type_node)
        names = [c for c in param.children if c.type in ("identifier", "field_identifier")]
        if names:
            for n in names:
                parts.append(f"{_node_text(n)}: {type_text}")
        else:
            parts.append(type_text)
    return ", ".join(parts)


def _extract_result_from_node(node) -> str:
    result_node = node.child_by_field_name("result")
    if result_node is None:
        return ""
    return f" -> {_node_text(result_node)}"


def _extract_receiver_type(method_node) -> str:
    receiver = method_node.child_by_field_name("receiver")
    if receiver is None:
        return ""
    for param in receiver.children:
        if param.type == "parameter_declaration":
            type_node = param.child_by_field_name("type")
            if type_node is not None:
                name = _node_text(type_node).lstrip("*")
                bracket = name.find("[")
                if bracket != -1:
                    name = name[:bracket]
                return name
    return ""


def _parse_method(node) -> MethodContract:
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) if name_node else ""
    params = _extract_params(node.child_by_field_name("parameters"))
    result = _extract_result_from_node(node)
    signature = f"({params}){result}"
    return MethodContract(name=name, signature=signature)


def _extract_struct_fields(struct_node) -> list[PropertyContract]:
    fields: list[PropertyContract] = []
    for child in struct_node.children:
        if child.type == "field_declaration_list":
            for field in child.children:
                if field.type == "field_declaration":
                    name_node = field.child_by_field_name("name")
                    type_node = field.child_by_field_name("type")
                    if name_node is not None and type_node is not None:
                        name = _node_text(name_node)
                        if _is_exported(name):
                            fields.append(
                                PropertyContract(name=name, signature=_node_text(type_node))
                            )
    return fields


def _extract_interface_methods(iface_node) -> list[MethodContract]:
    methods: list[MethodContract] = []
    for child in iface_node.children:
        if child.type == "method_elem":
            name_node = child.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            params = _extract_params(child.child_by_field_name("parameters"))
            result = _extract_result_from_node(child)
            signature = f"({params}){result}"
            methods.append(MethodContract(name=name, signature=signature))
    return methods


def _process_type_declaration(node, entities: dict[str, EntityContract], struct_names: set[str]) -> None:
    for child in node.children:
        if child.type != "type_spec":
            continue
        type_name_node = child.child_by_field_name("name")
        if type_name_node is None:
            continue
        type_name = _node_text(type_name_node)
        if not _is_exported(type_name):
            continue

        for inner in child.children:
            if inner.type == "struct_type":
                fields = _extract_struct_fields(inner)
                entities[type_name] = EntityContract(
                    name=type_name,
                    signature="",
                    properties=fields,
                    methods=[],
                )
                struct_names.add(type_name)
            elif inner.type == "interface_type":
                iface_methods = _extract_interface_methods(inner)
                entities[type_name] = EntityContract(
                    name=type_name,
                    signature="",
                    properties=[],
                    methods=iface_methods,
                )


def _process_function_declaration(node, routines: dict[str, RoutineContract]) -> None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return
    name = _node_text(name_node)
    if not _is_exported(name):
        return
    params = _extract_params(node.child_by_field_name("parameters"))
    result = _extract_result_from_node(node)
    signature = f"({params}){result}"
    routines[name] = RoutineContract(name=name, signature=signature)


def _process_method_declaration(node, methods_by_receiver: dict[str, list[MethodContract]]) -> None:
    recv_name = _extract_receiver_type(node)
    if not recv_name:
        return
    method = _parse_method(node)
    if not _is_exported(method.name):
        return
    methods_by_receiver.setdefault(recv_name, []).append(method)


def _parse_file(
    tree,
    entities: dict[str, EntityContract],
    routines: dict[str, RoutineContract],
    methods_by_receiver: dict[str, list[MethodContract]],
    struct_names: set[str],
) -> None:
    for node in tree.root_node.children:
        if node.type == "function_declaration":
            _process_function_declaration(node, routines)
        elif node.type == "method_declaration":
            _process_method_declaration(node, methods_by_receiver)
        elif node.type == "type_declaration":
            _process_type_declaration(node, entities, struct_names)


def golang_contract(cell_path: str) -> list[EntityContract | RoutineContract]:
    """Extract the contract (facade) from a Go package via tree-sitter.

    Args:
        cell_path: Path to the Go package directory.

    Returns:
        Sorted list of EntityContract and RoutineContract instances.
    """
    pkg_dir = Path(cell_path)
    go_files = sorted(f for f in pkg_dir.glob("*.go") if not f.name.endswith("_test.go"))

    if not go_files:
        return []

    entities: dict[str, EntityContract] = {}
    routines: dict[str, RoutineContract] = {}
    methods_by_receiver: dict[str, list[MethodContract]] = {}
    struct_names: set[str] = set()

    for go_file in go_files:
        source = go_file.read_bytes()
        tree = _PARSER.parse(source)
        _parse_file(tree, entities, routines, methods_by_receiver, struct_names)

    for recv_name, methods in methods_by_receiver.items():
        if recv_name in struct_names:
            entities[recv_name].methods.extend(methods)

    for entity in entities.values():
        entity.properties.sort(key=lambda p: p.name)
        entity.methods.sort(key=lambda m: m.name)

    sorted_entities = sorted(entities.values(), key=lambda e: e.name)
    sorted_routines = sorted(routines.values(), key=lambda r: r.name)

    return sorted_entities + sorted_routines
