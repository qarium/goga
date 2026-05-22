"""JavaScript contract extraction — extracts facade from JavaScript modules via tree-sitter."""

from __future__ import annotations

import re
from pathlib import Path

import tree_sitter_javascript as tsjs
from tree_sitter import Language, Parser

from ..data import EntityContract, MethodContract, PropertyContract, RoutineContract
from ..treesitter_utils import node_text as _node_text
from ..treesitter_utils import sort_contracts

JS_LANG = Language(tsjs.language())
_PARSER = Parser(JS_LANG)

_RE_PARAM_KEYWORD = re.compile(r"@param\s+")
_RE_RETURN_KEYWORD = re.compile(r"@returns?\s+")
_RE_TYPE_KEYWORD = re.compile(r"@type\s+")
_RE_PARAM_NAME = re.compile(r"\[?([\w$]+)(?:\s*=\s*[^\]\s]*)?\]?")


def _extract_braced_type(text: str, start_pos: int) -> str:
    """Extract {type} from text starting at start_pos using balanced brace matching."""
    brace_start = text.find("{", start_pos)
    if brace_start == -1:
        return ""
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start + 1 : i]
    return ""

_FUNCTION_TYPES = frozenset(
    {
        "function_declaration",
        "function_expression",
        "generator_function_declaration",
        "generator_function",
    }
)
_CLASS_TYPES = frozenset({"class_declaration", "class"})
_FUNC_EXPR_TYPES = frozenset({"arrow_function", "function_expression", "generator_function"})


def _extract_params(params_node) -> str:
    if params_node is None:
        return ""
    parts: list[str] = []
    for child in params_node.children:
        if child.type == "identifier":
            parts.append(_node_text(child))
        elif child.type == "assignment_pattern":
            left = child.child_by_field_name("left")
            if left is not None:
                parts.append(_node_text(left))
        elif child.type == "rest_pattern":
            for rc in child.children:
                if rc.type == "identifier":
                    parts.append(f"...{_node_text(rc)}")
                    break
        elif child.type in ("object_pattern", "array_pattern"):
            parts.append(_node_text(child))
    return ", ".join(parts)


def _extract_jsdoc(node) -> dict:  # noqa: C901, PLR0912
    jsdoc: dict = {"params": {}, "returns": "", "type": ""}
    _container_types = ("export_statement", "lexical_declaration", "variable_declaration")
    target = node
    if node.parent is not None and node.parent.type in _container_types:
        target = node.parent
    elif node.parent is not None and node.parent.type == "assignment_expression":
        # Handle module.exports = function() / => patterns
        target = node.parent.parent if node.parent.parent is not None else node.parent
    # Walk backward through comment siblings to find a JSDoc block
    prev = target.prev_named_sibling
    while prev is not None and prev.type == "comment":
        comment_text = _node_text(prev)
        if comment_text.startswith("/**"):
            # Found JSDoc — extract annotations
            for m in _RE_PARAM_KEYWORD.finditer(comment_text):
                type_str = _extract_braced_type(comment_text, m.end())
                # Skip past the entire {type} to find the name
                brace_start = comment_text.find("{", m.end())
                after_type = ""
                if brace_start != -1:
                    after_type = comment_text[brace_start:]
                    # Count braces to find the end of the type
                    depth = 0
                    skip_end = 0
                    for i, ch in enumerate(after_type):
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if depth == 0:
                                skip_end = i + 1
                                break
                    after_type = after_type[skip_end:]
                name_match = _RE_PARAM_NAME.match(after_type.lstrip())
                if name_match:
                    jsdoc["params"][name_match.group(1)] = type_str
            m_ret = _RE_RETURN_KEYWORD.search(comment_text)
            if m_ret:
                jsdoc["returns"] = _extract_braced_type(comment_text, m_ret.end())
            m_type = _RE_TYPE_KEYWORD.search(comment_text)
            if m_type:
                jsdoc["type"] = _extract_braced_type(comment_text, m_type.end())
            return jsdoc
        prev = prev.prev_named_sibling
    return jsdoc


def _build_signature(params_str: str, jsdoc: dict) -> str:
    param_names = [p.strip() for p in params_str.split(",") if p.strip()] if params_str else []
    typed_params = []
    for name in param_names:
        # Strip leading non-alpha chars (e.g. "...") for JSDoc lookup
        stripped = name.lstrip(".")
        jsdoc_type = jsdoc.get("params", {}).get(stripped, "")
        if jsdoc_type:
            prefix = name[: len(name) - len(stripped)] if len(name) != len(stripped) else ""
            typed_params.append(f"{prefix}{stripped}: {jsdoc_type}")
        else:
            typed_params.append(name)
    sig = f"({', '.join(typed_params)})"
    ret = jsdoc.get("returns", "")
    if ret:
        sig += f" -> {ret}"
    return sig


def _extract_class_methods(body_node) -> list[MethodContract]:
    methods: list[MethodContract] = []
    if body_node is None:
        return methods
    for member in body_node.children_by_field_name("member"):
        if member.type != "method_definition":
            continue
        name_node = member.child_by_field_name("name")
        if name_node is None or name_node.type == "private_property_identifier":
            continue
        name = _node_text(name_node)
        params = _extract_params(member.child_by_field_name("parameters"))
        jsdoc = _extract_jsdoc(member)
        signature = _build_signature(params, jsdoc)
        methods.append(MethodContract(name=name, signature=signature))
    return methods


def _extract_class_fields(body_node) -> list[PropertyContract]:
    fields: list[PropertyContract] = []
    if body_node is None:
        return fields
    for member in body_node.children_by_field_name("member"):
        if member.type != "field_definition":
            continue
        prop_node = member.child_by_field_name("property")
        if prop_node is None or prop_node.type == "private_property_identifier":
            continue
        name = _node_text(prop_node)
        jsdoc = _extract_jsdoc(member)
        sig = jsdoc.get("type", "")
        fields.append(PropertyContract(name=name, signature=sig))
    return fields


def _process_class_declaration(
    decl_node,
    entities: dict[str, EntityContract],
    export_name: str | None = None,
) -> None:
    if export_name is not None:
        name = export_name
    else:
        name_node = decl_node.child_by_field_name("name")
        if name_node is not None:
            name = _node_text(name_node)
        else:
            return
    body = decl_node.child_by_field_name("body")
    methods = _extract_class_methods(body)
    fields = _extract_class_fields(body)
    entities[name] = EntityContract(
        name=name,
        signature="()",
        properties=fields,
        methods=methods,
    )


def _process_function_declaration(
    decl_node,
    routines: dict[str, RoutineContract],
    export_name: str | None = None,
) -> None:
    if export_name is not None:
        name = export_name
    else:
        name_node = decl_node.child_by_field_name("name")
        if name_node is not None:
            name = _node_text(name_node)
        else:
            return
    params = _extract_params(decl_node.child_by_field_name("parameters"))
    jsdoc = _extract_jsdoc(decl_node)
    signature = _build_signature(params, jsdoc)
    routines[name] = RoutineContract(name=name, signature=signature)


def javascript_contract(cell_path: str) -> list[EntityContract | RoutineContract]:  # noqa: C901
    """Extract the contract (facade) from a JavaScript module.

    Args:
        cell_path: Path to the JavaScript module directory (containing index.js).

    Returns:
        Sorted list of EntityContract and RoutineContract instances.
    """
    pkg_dir = Path(cell_path)
    index_js = pkg_dir / "index.js"

    if not index_js.is_file():
        return []

    source = index_js.read_bytes()
    tree = _PARSER.parse(source)
    root = tree.root_node

    entities: dict[str, EntityContract] = {}
    routines: dict[str, RoutineContract] = {}
    declarations: dict[str, object] = {}

    # Pass 1: collect all non-export declarations
    for node in root.children:
        if node.type in _FUNCTION_TYPES or node.type in _CLASS_TYPES:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                declarations[_node_text(name_node)] = node
        elif node.type in ("lexical_declaration", "variable_declaration"):
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node is not None:
                        declarations[_node_text(name_node)] = child

    # Pass 2: process exports
    for node in root.children:
        if node.type == "export_statement":
            _process_export_statement(node, declarations, entities, routines)
        elif node.type == "expression_statement":
            _process_expression_statement(node, declarations, entities, routines)

    return sort_contracts(entities, routines)


def _process_export_statement(  # noqa: C901, PLR0912
    node,
    declarations: dict[str, object],
    entities: dict[str, EntityContract],
    routines: dict[str, RoutineContract],
) -> None:
    decl = node.child_by_field_name("declaration")
    if decl is not None:
        is_default = any(c.type == "default" for c in node.children)
        export_name = "default" if is_default else None
        if decl.type in _FUNCTION_TYPES:
            _process_function_declaration(decl, routines, export_name=export_name)
        elif decl.type in _CLASS_TYPES:
            _process_class_declaration(decl, entities, export_name=export_name)
        return

    value = node.child_by_field_name("value")
    if value is not None:
        if value.type in _FUNCTION_TYPES:
            _process_function_declaration(value, routines, export_name="default")
        elif value.type in _CLASS_TYPES:
            _process_class_declaration(value, entities, export_name="default")
        elif value.type == "arrow_function":
            _process_arrow_function(value, routines, export_name="default")
        return

    # export_clause: export { foo, bar } or export { foo as bar }
    for child in node.children:
        if child.type == "export_clause":
            for spec in child.children:
                if spec.type == "export_specifier":
                    name_node = spec.child_by_field_name("name")
                    alias_node = spec.child_by_field_name("alias")
                    if name_node is None:
                        continue
                    orig_name = _node_text(name_node)
                    exported_name = _node_text(alias_node) if alias_node is not None else orig_name
                    decl_node = declarations.get(orig_name)
                    if decl_node is None:
                        continue
                    if decl_node.type in _FUNCTION_TYPES:
                        _process_function_declaration(decl_node, routines, export_name=exported_name)
                    elif decl_node.type in _CLASS_TYPES:
                        _process_class_declaration(decl_node, entities, export_name=exported_name)
                    elif decl_node.type == "variable_declarator":
                        value = decl_node.child_by_field_name("value")
                        if value is not None and value.type in _CLASS_TYPES:
                            _process_class_declaration(value, entities, export_name=exported_name)
                        else:
                            _process_variable_declarator_as_routine(decl_node, routines, export_name=exported_name)
            return


def _process_expression_statement(  # noqa: C901, PLR0912, PLR0915
    node,
    declarations: dict[str, object],
    entities: dict[str, EntityContract],
    routines: dict[str, RoutineContract],
) -> None:
    expr = None
    for child in node.children:
        if child.type == "assignment_expression":
            expr = child
            break
    if expr is None:
        return
    left = expr.child_by_field_name("left")
    right = expr.child_by_field_name("right")
    if left is None or right is None:
        return
    if left.type != "member_expression":
        return
    left_text = _node_text(left)
    if left_text != "module.exports":
        return

    if right.type == "identifier":
        name = _node_text(right)
        decl_node = declarations.get(name)
        if decl_node is not None:
            if decl_node.type in _FUNCTION_TYPES:
                _process_function_declaration(decl_node, routines)
            elif decl_node.type in _CLASS_TYPES:
                _process_class_declaration(decl_node, entities)
            elif decl_node.type == "variable_declarator":
                value = decl_node.child_by_field_name("value")
                if value is not None and value.type in _CLASS_TYPES:
                    _process_class_declaration(value, entities, export_name=name)
                else:
                    _process_variable_declarator_as_routine(decl_node, routines)
    elif right.type in _FUNC_EXPR_TYPES:
        if right.type == "arrow_function":
            _process_arrow_function(right, routines, export_name="default")
        else:
            _process_function_declaration(right, routines, export_name="default")
    elif right.type in _CLASS_TYPES:
        _process_class_declaration(right, entities, export_name="default")
    elif right.type == "object":
        for child in right.children:
            if child.type == "method_definition":
                name_node = child.child_by_field_name("name")
                if name_node is None:
                    continue
                name = _node_text(name_node)
                params = _extract_params(child.child_by_field_name("parameters"))
                jsdoc = _extract_jsdoc(child)
                signature = _build_signature(params, jsdoc)
                routines[name] = RoutineContract(name=name, signature=signature)
            elif child.type == "pair":
                key_node = child.child_by_field_name("key")
                if key_node is not None:
                    name = _node_text(key_node)
                    if key_node.type == "string":
                        name = name.strip("\"'")
                    val_node = child.child_by_field_name("value")
                    if val_node is not None and val_node.type in _FUNC_EXPR_TYPES:
                        params = _extract_params(val_node.child_by_field_name("parameters"))
                        jsdoc = _extract_jsdoc(child)
                        signature = _build_signature(params, jsdoc)
                        routines[name] = RoutineContract(name=name, signature=signature)
                    elif val_node is not None and val_node.type in _CLASS_TYPES:
                        _process_class_declaration(val_node, entities, export_name=name)
            elif child.type == "shorthand_property_identifier":
                name = _node_text(child)
                decl_node = declarations.get(name)
                if decl_node is not None:
                    if decl_node.type in _FUNCTION_TYPES:
                        _process_function_declaration(decl_node, routines)
                    elif decl_node.type in _CLASS_TYPES:
                        _process_class_declaration(decl_node, entities)
                    elif decl_node.type == "variable_declarator":
                        value = decl_node.child_by_field_name("value")
                        if value is not None and value.type in _CLASS_TYPES:
                            _process_class_declaration(value, entities, export_name=name)
                        else:
                            _process_variable_declarator_as_routine(decl_node, routines)


def _process_arrow_function(
    arrow_node,
    routines: dict[str, RoutineContract],
    export_name: str = "default",
    jsdoc: dict | None = None,
) -> None:
    params = _extract_params(arrow_node.child_by_field_name("parameters"))
    if not params:
        single_param = arrow_node.child_by_field_name("parameter")
        if single_param is not None:
            params = _node_text(single_param)
    if jsdoc is None:
        jsdoc = _extract_jsdoc(arrow_node)
    signature = _build_signature(params, jsdoc)
    routines[export_name] = RoutineContract(name=export_name, signature=signature)


def _process_variable_declarator_as_routine(
    declarator,
    routines: dict[str, RoutineContract],
    export_name: str | None = None,
) -> None:
    name_node = declarator.child_by_field_name("name")
    value = declarator.child_by_field_name("value")
    if name_node is None:
        return
    name = _node_text(name_node) if export_name is None else export_name
    if value is not None and value.type in _FUNC_EXPR_TYPES:
        if value.type == "arrow_function":
            jsdoc = _extract_jsdoc(declarator)
            _process_arrow_function(value, routines, export_name=name, jsdoc=jsdoc)
            return
        params = _extract_params(value.child_by_field_name("parameters"))
        jsdoc = _extract_jsdoc(declarator)
        signature = _build_signature(params, jsdoc)
        routines[name] = RoutineContract(name=name, signature=signature)
