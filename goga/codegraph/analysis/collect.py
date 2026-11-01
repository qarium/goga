"""First analysis stage — collect the facts of every source file.

Each file is read and parsed exactly once with the tree-sitter grammar of
the project language; the per-language extractors turn the parse tree into
declarations, imports, explicit exports, and the module declaration. Any
ERROR or MISSING parse node fails closed with an error naming the file.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Language, Node, Parser

from ..facts import Declaration, FileFacts, ImportRef

_GRAMMAR_MODULES: dict[str, str] = {
    "python": "tree_sitter_python",
    "golang": "tree_sitter_go",
    "javascript": "tree_sitter_javascript",
    "kotlin": "tree_sitter_kotlin",
    "swift": "tree_sitter_swift",
}

_PARSERS: dict[str, Parser] = {}

_Extraction = tuple[list[Declaration], list[ImportRef], list[str], str]
_Extractor = Callable[[Node, Path], _Extraction]


def collect_facts(files: list[Path], language: str) -> list[FileFacts]:
    """Collect the facts of every source file with the language grammar.

    Args:
        files: Source files to analyze, relative to the project root.
        language: The single configured language — python, golang,
            javascript, kotlin, swift.

    Returns:
        One ``FileFacts`` per input file, in input order.

    Raises:
        ValueError: When the language is not supported, or when a source
            file fails to parse — the error names the file.
    """
    if language not in _GRAMMAR_MODULES:
        raise ValueError(f"unsupported language: {language!r}; expected one of {sorted(_GRAMMAR_MODULES)}")

    parser = _parser_for(language)
    extractor = _EXTRACTORS[language]
    facts: list[FileFacts] = []

    for file in files:
        source = file.read_bytes()
        tree = parser.parse(source)

        if tree.root_node.has_error:
            raise ValueError(f"unparseable source file: {file}")

        try:
            declarations, imports, exports, module = extractor(tree.root_node, file)
        except RecursionError as error:
            raise ValueError(f"unparseable source file: {file}") from error

        facts.append(
            FileFacts(
                path=file,
                declarations=declarations,
                imports=imports,
                exports=exports,
                module=module,
            )
        )

    return facts


def _parser_for(language: str) -> Parser:
    """Return the process-wide parser singleton of ``language``."""
    parser = _PARSERS.get(language)

    if parser is None:
        grammar = importlib.import_module(_GRAMMAR_MODULES[language])
        parser = Parser(Language(grammar.language()))
        _PARSERS[language] = parser

    return parser


def _text(node: Node | None) -> str:
    """Decode the UTF-8 text of ``node``, or an empty string for None."""
    if node is None:
        return ""

    return node.text.decode("utf-8")


def _first_child_by_types(node: Node, types: frozenset[str]) -> Node | None:
    """Return the first direct child of ``node`` whose type is in ``types``."""
    for child in node.children:
        if child.type in types:
            return child

    return None


_MIN_QUOTED_LENGTH = 2


def _unquote(text: str) -> str:
    """Strip one matching pair of surrounding quotes from ``text``."""
    if len(text) >= _MIN_QUOTED_LENGTH and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]

    return text


# --- shared member-access chain machinery (python attributes, go selectors, js members) ---


@dataclass(frozen=True, kw_only=True)
class _ChainSpec:
    """Grammar shape of one language's member-access chains.

    Attributes:
        chain_type: Node type of a member-access chain link.
        field_types: Node types of the accessed member segment.
    """

    chain_type: str = ""
    field_types: frozenset[str] = frozenset()


_PY_CHAIN = _ChainSpec(
    chain_type="attribute",
    field_types=frozenset({"identifier"}),
)
_GO_CHAIN = _ChainSpec(
    chain_type="selector_expression",
    field_types=frozenset({"field_identifier"}),
)
_JS_CHAIN = _ChainSpec(
    chain_type="member_expression",
    field_types=frozenset({"property_identifier"}),
)


def _chain_path(node: Node, spec: _ChainSpec) -> list[str] | None:
    """Return the pure dotted path of ``node``, or None when not a chain."""
    if node.type == "identifier":
        return [_text(node)]

    if node.type != spec.chain_type:
        return None

    base_child = None
    field_child = None

    for child in node.children:
        if child.type in (spec.chain_type, "identifier"):
            if base_child is None:
                base_child = child

            field_child = child
        elif child.type in spec.field_types:
            field_child = child

    if base_child is None or field_child is None or base_child is field_child:
        return None

    base_path = _chain_path(base_child, spec)

    if base_path is None:
        return None

    return [*base_path, _text(field_child)]


def _chain_paths(root: Node, spec: _ChainSpec) -> list[list[str]]:
    """Collect the dotted paths of every member-access chain in the tree."""
    paths: list[list[str]] = []

    _collect_chain_paths(root, spec, paths)

    return paths


def _collect_chain_paths(node: Node, spec: _ChainSpec, paths: list[list[str]]) -> None:
    """Accumulate the chain paths of the subtree into ``paths``."""
    if node.type == spec.chain_type:
        path = _chain_path(node, spec)

        if path is not None:
            paths.append(path)

    for child in node.children:
        _collect_chain_paths(child, spec, paths)


def _first_after_prefix(chain: list[str], prefix: list[str]) -> str | None:
    """Return the first chain segment after the longest matching prefix."""
    common = 0

    while common < len(prefix) and common < len(chain) and chain[common] == prefix[common]:
        common += 1

    if common == 0 or common == len(chain):
        return None

    return chain[common]


def _members_after_binding(chains: list[list[str]], binding: str) -> list[str]:
    """Return the sorted unique member segments accessed through ``binding``."""
    names: set[str] = set()

    for chain in chains:
        if chain and chain[0] == binding and len(chain) > 1:
            names.update(chain[1:])

    return sorted(names)


def _collect_identifiers(
    node: Node,
    identifier_type: str,
    skip_types: frozenset[str],
    names: set[str],
) -> None:
    """Accumulate the texts of ``identifier_type`` nodes outside skipped subtrees."""
    if node.type in skip_types:
        return

    if node.type == identifier_type:
        names.add(_text(node))

    for child in node.children:
        _collect_identifiers(child, identifier_type, skip_types, names)


# --- python ---


_PY_DECLARATION_TYPES = frozenset({"function_definition", "class_definition"})
_PY_IMPORT_TYPES = frozenset({"import_statement", "import_from_statement"})


def _python_facts(root: Node, path: Path) -> _Extraction:
    """Extract python declarations, imports, and explicit exports."""
    declarations: list[Declaration] = []
    imports: list[ImportRef] = []
    exports: list[str] = []
    bindings: list[str] = []
    plain_specifiers: list[str] = []
    wildcard_imports: list[tuple[str, bool]] = []

    for child in root.children:
        if child.type == "import_statement":
            _python_plain_imports(child, path, imports, bindings, plain_specifiers)
        elif child.type == "import_from_statement":
            _python_from_import(child, path, imports, bindings, wildcard_imports)
        else:
            _python_toplevel_statement(child, path, declarations, bindings, exports)

    if path.name == "__init__.py":
        _python_binding_declarations(declarations, bindings, path)

    _python_usage_refs(root, path, plain_specifiers, wildcard_imports, imports)

    return declarations, imports, exports, ""


def _python_plain_imports(
    statement: Node,
    path: Path,
    imports: list[ImportRef],
    bindings: list[str],
    plain_specifiers: list[str],
) -> None:
    """Record one base ref per plain import; collect bindings for __init__ files."""
    for item in statement.children:
        if item.type == "dotted_name":
            specifier = _text(item)
            imports.append(ImportRef(source=path, specifier=specifier))
            bindings.append(specifier.split(".")[0])
            plain_specifiers.append(specifier)
        elif item.type == "aliased_import":
            name = _text(item.child_by_field_name("name"))
            imports.append(ImportRef(source=path, specifier=name))
            bindings.append(_text(item.child_by_field_name("alias")))


def _python_from_import(
    statement: Node,
    path: Path,
    imports: list[ImportRef],
    bindings: list[str],
    wildcard_imports: list[tuple[str, bool]],
) -> None:
    """Record the base ref of one from-import; collect local bindings."""
    module = statement.child_by_field_name("module_name")
    specifier = _text(module)
    is_relative = module is not None and module.type == "relative_import"
    names: list[str] = []

    for item in statement.children_by_field_name("name"):
        if item.type == "dotted_name":
            names.append(_text(item))
            bindings.append(_text(item))
        elif item.type == "aliased_import":
            names.append(_text(item.child_by_field_name("name")))
            bindings.append(_text(item.child_by_field_name("alias")))

    is_wildcard = _first_child_by_types(statement, frozenset({"wildcard_import"})) is not None

    imports.append(
        ImportRef(
            source=path,
            specifier=specifier,
            names=names,
            is_relative=is_relative,
            is_wildcard=is_wildcard,
        )
    )

    if is_wildcard:
        wildcard_imports.append((specifier, is_relative))


def _python_toplevel_statement(
    statement: Node,
    path: Path,
    declarations: list[Declaration],
    bindings: list[str],
    exports: list[str],
) -> None:
    """Record one definition or assignment statement of the file top level."""
    definition = statement

    if statement.type == "decorated_definition":
        definition = _first_child_by_types(statement, _PY_DECLARATION_TYPES) or statement

    if definition.type in _PY_DECLARATION_TYPES:
        name = _text(definition.child_by_field_name("name"))
        declarations.append(Declaration(path=path, name=name, is_public=not name.startswith("_")))
        bindings.append(name)

        return

    if statement.type != "expression_statement":
        return

    for child in statement.children:
        if child.type == "assignment":
            _python_assignment(child, bindings, exports)


def _python_assignment(assignment: Node, bindings: list[str], exports: list[str]) -> None:
    """Extend exports for an ``__all__`` list assignment, bindings otherwise."""
    left = assignment.child_by_field_name("left")
    right = assignment.child_by_field_name("right")

    if _text(left) == "__all__" and right is not None and right.type == "list":
        bindings.append("__all__")

        for element in _python_string_elements(right):
            if element not in exports:
                exports.append(element)

        return

    bindings.extend(_python_target_names(left))


def _python_string_elements(list_node: Node) -> list[str]:
    """Return the decoded elements of a string list literal."""
    return [_python_string_value(item) for item in list_node.children if item.type in ("string", "concatenated_string")]


def _python_string_value(string_node: Node) -> str:
    """Return the decoded text of one string element, quotes and prefix excluded."""
    if string_node.type == "concatenated_string":
        return "".join(_python_string_value(child) for child in string_node.children if child.type == "string")

    content = "".join(_text(child) for child in string_node.children if child.type == "string_content")

    return content or _text(string_node)[1:-1]


def _python_target_names(left: Node | None) -> list[str]:
    """Return the identifier names bound by an assignment target."""
    if left is None:
        return []

    if left.type == "identifier":
        return [_text(left)]

    if left.type in ("pattern_list", "tuple_pattern"):
        return [_text(child) for child in left.children if child.type == "identifier"]

    return []


def _python_binding_declarations(
    declarations: list[Declaration],
    bindings: list[str],
    path: Path,
) -> None:
    """Record every not-yet-recorded binding of a package __init__ file."""
    recorded = {declaration.name for declaration in declarations}

    for name in bindings:
        if name in recorded:
            continue

        declarations.append(Declaration(path=path, name=name, is_public=not name.startswith("_")))
        recorded.add(name)


def _python_usage_refs(
    root: Node,
    path: Path,
    plain_specifiers: list[str],
    wildcard_imports: list[tuple[str, bool]],
    imports: list[ImportRef],
) -> None:
    """Record one usage ref per plain and per wildcard import (review fix R1)."""
    if not plain_specifiers and not wildcard_imports:
        return

    chains = _chain_paths(root, _PY_CHAIN)
    used_identifiers: set[str] = set()

    if wildcard_imports:
        _collect_identifiers(root, "identifier", _PY_IMPORT_TYPES, used_identifiers)

    for specifier in plain_specifiers:
        segments = specifier.split(".")
        names = sorted(
            {name for name in (_first_after_prefix(chain, segments) for chain in chains) if name is not None}
        )
        imports.append(ImportRef(source=path, specifier=specifier, names=names))

    for specifier, is_relative in wildcard_imports:
        imports.append(
            ImportRef(
                source=path,
                specifier=specifier,
                names=sorted(used_identifiers),
                is_relative=is_relative,
                is_wildcard=True,
            )
        )


# --- golang ---


def _golang_facts(root: Node, path: Path) -> _Extraction:
    """Extract golang package-scope declarations and import path refs."""
    declarations: list[Declaration] = []
    imports: list[ImportRef] = []
    import_specs: list[tuple[str, bool]] = []

    for child in root.children:
        if child.type == "function_declaration":
            _golang_record_declaration(declarations, path, _text(child.child_by_field_name("name")))
        elif child.type == "type_declaration":
            for spec in child.children:
                if spec.type == "type_spec":
                    name = _text(spec.child_by_field_name("name"))
                    _golang_record_declaration(declarations, path, name)
        elif child.type in ("var_declaration", "const_declaration"):
            for spec in _golang_declaration_specs(child):
                _golang_record_declaration(declarations, path, _golang_spec_name(spec))
        elif child.type == "import_declaration":
            _golang_imports(child, path, imports, import_specs)

    _golang_usage_refs(root, path, import_specs, imports)

    return declarations, imports, [], ""


def _golang_record_declaration(declarations: list[Declaration], path: Path, name: str) -> None:
    """Record one package-scope declaration; exported names start upper-case."""
    if not name:
        return

    declarations.append(Declaration(path=path, name=name, is_public=name[:1].isupper()))


def _golang_spec_name(spec: Node) -> str:
    """Return the name of a var or const spec."""
    name = _text(spec.child_by_field_name("name"))

    if name:
        return name

    return _text(_first_child_by_types(spec, frozenset({"identifier"})))


def _golang_imports(
    declaration: Node,
    path: Path,
    imports: list[ImportRef],
    import_specs: list[tuple[str, bool]],
) -> None:
    """Record one base ref per import spec, aliased imports flagged."""
    for child in declaration.children:
        for item in _golang_import_items(child):
            specifier = _unquote(_text(item.child_by_field_name("path")))
            aliased = item.child_by_field_name("name") is not None
            imports.append(ImportRef(source=path, specifier=specifier))
            import_specs.append((specifier, aliased))


def _golang_declaration_specs(declaration: Node) -> list[Node]:
    """Return the var and const specs of one declaration, grouped form included."""
    specs: list[Node] = []

    for child in declaration.children:
        if child.type in ("var_spec", "const_spec"):
            specs.append(child)
        elif child.type in ("var_spec_list", "const_spec_list"):
            specs.extend(spec for spec in child.children if spec.type in ("var_spec", "const_spec"))

    return specs


def _golang_import_items(node: Node) -> list[Node]:
    """Return the import specs of one child of an import declaration."""
    if node.type == "import_spec":
        return [node]

    if node.type == "import_spec_list":
        return [child for child in node.children if child.type == "import_spec"]

    return []


def _golang_usage_refs(
    root: Node,
    path: Path,
    import_specs: list[tuple[str, bool]],
    imports: list[ImportRef],
) -> None:
    """Record one usage ref per non-aliased import (review fix R1)."""
    if all(aliased for _, aliased in import_specs):
        return

    chains = _chain_paths(root, _GO_CHAIN)

    for specifier, aliased in import_specs:
        if aliased:
            continue

        binding = specifier.rsplit("/", 1)[-1]
        imports.append(
            ImportRef(
                source=path,
                specifier=specifier,
                names=_members_after_binding(chains, binding),
            )
        )


# --- javascript ---


_JS_DECLARATION_TYPES = frozenset(
    {
        "function_declaration",
        "class_declaration",
        "generator_function_declaration",
        "lexical_declaration",
        "variable_declaration",
    }
)
_JS_NAMED_DECLARATION_TYPES = frozenset({"function_declaration", "class_declaration", "generator_function_declaration"})


def _javascript_facts(root: Node, path: Path) -> _Extraction:
    """Extract javascript declarations, ESM imports, and export names."""
    declarations: list[Declaration] = []
    imports: list[ImportRef] = []
    clause_names: list[str] = []
    default_names: list[str] = []
    exported_locals: set[str] = set()
    bare_names: list[str] = []
    namespace_imports: list[tuple[str, bool, str]] = []

    for child in root.children:
        if child.type == "import_statement":
            _javascript_import(child, path, imports, namespace_imports)
        elif child.type == "export_statement":
            clause, default, locals_exported = _javascript_export(child, path, declarations)
            clause_names.extend(clause)
            default_names.extend(default)
            exported_locals.update(locals_exported)
        elif child.type in _JS_DECLARATION_TYPES:
            name = _javascript_declaration_name(child)

            if name:
                bare_names.append(name)

    for name in bare_names:
        declarations.append(Declaration(path=path, name=name, is_public=name in exported_locals))

    exports = _deduplicated([*clause_names, *default_names])

    _javascript_usage_refs(root, path, namespace_imports, imports)

    return declarations, imports, exports, ""


def _deduplicated(names: list[str]) -> list[str]:
    """Return ``names`` without duplicates, first occurrence order kept."""
    return list(dict.fromkeys(names))


def _javascript_declaration_name(declaration: Node) -> str:
    """Return the declared name, or an empty string for anonymous nodes."""
    if declaration.type in _JS_NAMED_DECLARATION_TYPES:
        return _text(declaration.child_by_field_name("name"))

    declarator = _first_child_by_types(declaration, frozenset({"variable_declarator"}))

    if declarator is None:
        return ""

    return _text(declarator.child_by_field_name("name"))


def _javascript_import(
    statement: Node,
    path: Path,
    imports: list[ImportRef],
    namespace_imports: list[tuple[str, bool, str]],
) -> None:
    """Record the base ref of one ESM import statement."""
    specifier = _unquote(_text(statement.child_by_field_name("source")))
    is_relative = specifier.startswith(".") or specifier.startswith("/")
    names: list[str] = []
    is_wildcard = False
    alias = ""

    clause = _first_child_by_types(statement, frozenset({"import_clause"}))

    if clause is not None:
        for item in clause.children:
            if item.type == "identifier":
                names.append("default")
            elif item.type == "named_imports":
                names.extend(_javascript_named_imports(item))
            elif item.type == "namespace_import":
                is_wildcard = True
                alias = _text(_first_child_by_types(item, frozenset({"identifier"})))

    imports.append(
        ImportRef(
            source=path,
            specifier=specifier,
            names=names,
            is_relative=is_relative,
            is_wildcard=is_wildcard,
        )
    )

    if is_wildcard:
        namespace_imports.append((specifier, is_relative, alias))


def _javascript_named_imports(named_imports: Node) -> list[str]:
    """Return the imported (pre-alias) names of a named-imports clause."""
    return [
        _text(spec.child_by_field_name("name")) for spec in named_imports.children if spec.type == "import_specifier"
    ]


def _javascript_export(
    statement: Node,
    path: Path,
    declarations: list[Declaration],
) -> tuple[list[str], list[str], set[str]]:
    """Record exported declarations and return the export names of the statement.

    Args:
        statement: One ``export_statement`` node of the file top level.
        path: File that contains the statement.
        declarations: Declaration accumulator; exported declarations are
            appended in place.

    Returns:
        The exported clause names, the names of named default exports, and
        the locally bound names re-exported through export clauses.
    """
    declaration = statement.child_by_field_name("declaration")

    if declaration is not None:
        name = _javascript_declaration_name(declaration)

        if name:
            declarations.append(Declaration(path=path, name=name, is_public=True))

            if _first_child_by_types(statement, frozenset({"default"})) is not None:
                return ([], [name], set())

        return ([], [], set())

    clause_names: list[str] = []
    exported_locals: set[str] = set()

    for clause in statement.children:
        if clause.type != "export_clause":
            continue

        for spec in clause.children:
            if spec.type != "export_specifier":
                continue

            local = _text(spec.child_by_field_name("name"))
            alias = spec.child_by_field_name("alias")
            exported = _text(alias) if alias is not None else local
            clause_names.append(exported)
            exported_locals.add(local)

    return (clause_names, [], exported_locals)


def _javascript_usage_refs(
    root: Node,
    path: Path,
    namespace_imports: list[tuple[str, bool, str]],
    imports: list[ImportRef],
) -> None:
    """Record one usage ref per namespace import (review fix R1)."""
    if not namespace_imports:
        return

    chains = _chain_paths(root, _JS_CHAIN)

    for specifier, is_relative, alias in namespace_imports:
        imports.append(
            ImportRef(
                source=path,
                specifier=specifier,
                names=_members_after_binding(chains, alias),
                is_relative=is_relative,
                is_wildcard=True,
            )
        )


# --- kotlin ---


_KOTLIN_DECLARATION_TYPES = frozenset(
    {
        "function_declaration",
        "class_declaration",
        "object_declaration",
        "type_alias",
        "property_declaration",
    }
)


def _kotlin_facts(root: Node, path: Path) -> _Extraction:
    """Extract kotlin declarations, qualified imports, and the package module."""
    declarations: list[Declaration] = []
    imports: list[ImportRef] = []
    module = ""
    wildcard_specifiers: list[str] = []

    for child in root.children:
        if child.type == "package_header":
            module = _text(_first_child_by_types(child, frozenset({"qualified_identifier"})))
        elif child.type == "import":
            _kotlin_import(child, path, imports, wildcard_specifiers)
        elif child.type in _KOTLIN_DECLARATION_TYPES:
            name = _kotlin_declaration_name(child)

            if name:
                is_public = _kotlin_is_public(child)
                declarations.append(Declaration(path=path, name=name, is_public=is_public))

    _kotlin_usage_refs(root, path, wildcard_specifiers, imports)

    return declarations, imports, [], module


def _kotlin_declaration_name(declaration: Node) -> str:
    """Return the plain identifier name of a top-level declaration."""
    if declaration.type == "property_declaration":
        variable = _first_child_by_types(declaration, frozenset({"variable_declaration"}))

        if variable is None:
            return ""

        return _text(_first_child_by_types(variable, frozenset({"identifier"})))

    return _text(_first_child_by_types(declaration, frozenset({"identifier"})))


def _kotlin_is_public(declaration: Node) -> bool:
    """Return True for an explicit or implicit public declaration."""
    modifiers = _first_child_by_types(declaration, frozenset({"modifiers"}))

    if modifiers is None:
        return True

    visibility = _first_child_by_types(modifiers, frozenset({"visibility_modifier"}))

    if visibility is None:
        return True

    return _text(visibility) == "public"


def _kotlin_import(
    statement: Node,
    path: Path,
    imports: list[ImportRef],
    wildcard_specifiers: list[str],
) -> None:
    """Record one import ref; a trailing star marks the wildcard form."""
    qualified = _first_child_by_types(statement, frozenset({"qualified_identifier"}))

    if qualified is None:
        return

    specifier = _text(qualified)

    if _first_child_by_types(statement, frozenset({"*"})) is not None:
        imports.append(ImportRef(source=path, specifier=specifier, is_wildcard=True))
        wildcard_specifiers.append(specifier)

        return

    imports.append(ImportRef(source=path, specifier=specifier, names=[specifier.rsplit(".", 1)[-1]]))


def _kotlin_usage_refs(
    root: Node,
    path: Path,
    wildcard_specifiers: list[str],
    imports: list[ImportRef],
) -> None:
    """Record one usage ref per wildcard import (review fix R1)."""
    if not wildcard_specifiers:
        return

    used_identifiers: set[str] = set()

    _collect_identifiers(root, "identifier", frozenset({"import"}), used_identifiers)

    for specifier in wildcard_specifiers:
        imports.append(
            ImportRef(
                source=path,
                specifier=specifier,
                names=sorted(used_identifiers),
                is_wildcard=True,
            )
        )


# --- swift ---


_SWIFT_DECLARATION_TYPES = frozenset(
    {
        "function_declaration",
        "protocol_declaration",
        "init_declaration",
        "property_declaration",
        "typealias_declaration",
    }
)
_SWIFT_PUBLIC_MODIFIERS = frozenset({"public", "open"})


def _swift_facts(root: Node, path: Path) -> _Extraction:
    """Extract swift declarations, module imports, and used type names."""
    declarations: list[Declaration] = []
    imports: list[ImportRef] = []

    for child in root.children:
        if child.type == "import_declaration":
            specifier = _text(_first_child_by_types(child, frozenset({"identifier"})))
            imports.append(ImportRef(source=path, specifier=specifier))
        elif child.type == "class_declaration":
            _swift_class_declaration(child, path, declarations)
        elif child.type in _SWIFT_DECLARATION_TYPES:
            _swift_record_declaration(child, path, declarations)

    used_type_names: set[str] = set()

    _collect_identifiers(root, "type_identifier", frozenset({"import_declaration"}), used_type_names)
    imports.append(ImportRef(source=path, names=sorted(used_type_names)))

    return declarations, imports, [], ""


def _swift_class_declaration(
    declaration: Node,
    path: Path,
    declarations: list[Declaration],
) -> None:
    """Record a class-kind declaration; extensions declare no new name."""
    kind = _text(declaration.child_by_field_name("declaration_kind"))

    if kind == "extension":
        return

    _swift_record_declaration(declaration, path, declarations)


def _swift_record_declaration(
    declaration: Node,
    path: Path,
    declarations: list[Declaration],
) -> None:
    """Record one declaration; public and open are the public modifiers."""
    name = _text(declaration.child_by_field_name("name"))

    if not name:
        return

    modifiers = _first_child_by_types(declaration, frozenset({"modifiers"}))
    visibility = _first_child_by_types(modifiers, frozenset({"visibility_modifier"})) if modifiers is not None else None
    is_public = _text(visibility) in _SWIFT_PUBLIC_MODIFIERS

    declarations.append(Declaration(path=path, name=name, is_public=is_public))


_EXTRACTORS: dict[str, _Extractor] = {
    "python": _python_facts,
    "golang": _golang_facts,
    "javascript": _javascript_facts,
    "kotlin": _kotlin_facts,
    "swift": _swift_facts,
}
