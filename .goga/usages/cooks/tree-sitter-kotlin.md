# tree-sitter + tree-sitter-kotlin

## Purpose
Python bindings for incremental parsing. tree-sitter-kotlin is a Kotlin grammar.

Node inventory verified against tree-sitter-kotlin **1.1.0** (the pinned
`>=1.1.0` line): declaration/import/package names are plain `identifier`
nodes — the grammar has no `simple_identifier`, `type_identifier`,
`import_header`, `import_alias`, or `wildcard_import` nodes.

## Installation
pip install tree-sitter tree-sitter-kotlin

## Basic pattern for parsing a Kotlin file

```python
import tree_sitter_kotlin as tskotlin
from tree_sitter import Language, Parser

KOTLIN_LANG = Language(tskotlin.language())

parser = Parser(KOTLIN_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node
```

## Key Kotlin AST node types

### Declarations
- `function_declaration` — function (field: receiver; children: modifiers, type_parameters, identifier(name), function_value_parameters, _type(return), function_body)
- `property_declaration` — property (field: receiver; children: modifiers, binding_pattern_kind(val/var), variable_declaration, property_delegate, getter, setter)
- `class_declaration` — class/interface/enum/annotation/data/sealed (children: modifiers, identifier(name), type_parameters, primary_constructor, class_body/enum_class_body)
- `object_declaration` — object (children: modifiers, identifier(name), class_body)
- `companion_object` — companion object (children: modifiers, identifier(name), class_body)
- `type_alias` — type alias (children: identifier(name), type_parameters, _type)
- `secondary_constructor` — secondary constructor (children: modifiers, function_value_parameters, constructor_delegation_call, _block)
- `anonymous_initializer` — init block (children: _block)

### Constructor and parameters
- `primary_constructor` — primary constructor (children: class_parameter...)
- `class_parameter` — class constructor parameter (children: modifiers, binding_pattern_kind(val/var), identifier(name), _type, default)
- `function_value_parameters` — function parameter list (children: parameter_modifiers, parameter, default)
- `parameter` — parameter (children: identifier(name), _type)

### Bodies
- `function_body` — function body (block or expression body via `=`)
- `class_body` — class body (children: declarations)
- `enum_class_body` — enum body (children: enum_entry, declarations)
- `control_structure_body` — control structure body (block or single expression)
- `statements` — list of statements inside a block

### Types
- `user_type` — user-defined type (children: identifier, type_arguments)
- `nullable_type` — nullable type `Type?` (children: user_type/parenthesized_type, quest)
- `function_type` — function type `(Params) -> Ret` (field: receiver; children: function_type_parameters, _type)
- `parenthesized_type` — type in parentheses `(Type)`
- `receiver_type` — receiver type for extensions (children: type_modifiers, user_type/nullable_type)
- `type_parameters` — `<T, U>` (children: type_parameter)
- `type_arguments` — `<Arg>` (children: type_projection)
- `type_modifiers` — type modifiers (children: annotation, suspend)

### Names and identifiers
- `identifier` — identifier (declaration name, parameter name, type component, or enum entry; grammar 1.1.0 uses plain `identifier` everywhere)
- `qualified_identifier` — dotted name (children: identifier separated by `.`)
- `binding_pattern_kind` — `val` or `var`

### Modifiers
- `modifiers` — modifier container (children: annotation, class_modifier, visibility_modifier, ...)
- `visibility_modifier` — `public`, `private`, `internal`, `protected`
- `class_modifier` — `sealed`, `annotation`, `data`, `inner`, `value`
- `member_modifier` — `override`, `lateinit`
- `function_modifier` — `tailrec`, `operator`, `infix`, `inline`, `external`, `suspend`
- `property_modifier` — `const`
- `inheritance_modifier` — `abstract`, `final`, `open`
- `parameter_modifier` — `vararg`, `noinline`, `crossinline`
- `platform_modifier` — `expect`, `actual`
- `variance_modifier` — `in`, `out`
- `reification_modifier` — `reified`

### Annotations
- `annotation` — annotation (children: use_site_target, user_type/constructor_invocation)
- `use_site_target` — annotation target: `field`, `property`, `get`, `set`, `receiver`, `param`, `setparam`, `delegate`

### Enum
- `enum_entry` — enum element (children: modifiers, identifier(name), value_arguments, class_body)

### Expressions
- `call_expression` — function call (children: _expression, call_suffix)
- `navigation_expression` — member access `a.b` (children: _expression, navigation_suffix)
- `indexing_expression` — indexing `a[i]` (children: _expression, indexing_suffix)
- `as_expression` — type cast `x as Type` (children: _expression, _type)
- `elvis_expression` — elvis `x ?: y` (children: _expression)
- `range_expression` — range `a..b`, `a..<b` (children: _expression)
- `lambda_literal` — lambda `{ params -> body }` (children: lambda_parameters, statements)
- `anonymous_function` — anonymous function `fun(params) { body }` (children: function_value_parameters, function_body)
- `if_expression` — if (fields: condition, consequence, alternative)
- `when_expression` — when (children: when_subject, when_entry)
- `try_expression` — try/catch/finally (children: _block, catch_block, finally_block)
- `string_literal` — string with interpolation (children: string_content, interpolated_expression, interpolated_identifier)
- `callable_reference` — function reference `Class::method` (children: identifier, identifier)
- `this_expression` — `this` or `this@Label`
- `super_expression` — `super` or `super<Type>`
- `jump_expression` — return, throw, continue, break
- `spread_expression` — spread `*args` (children: _expression)
- `object_literal` — object expression `object : Base { ... }`
- `collection_literal` — `[a, b, c]`

### When
- `when_entry` — when branch (children: when_condition/guard_condition, control_structure_body)
- `when_condition` — branch condition (children: _expression, range_test, type_test)
- `when_subject` — when subject `when(x)` (children: _expression)
- `guard_condition` — guard condition in when-entry (children: _expression)

### Delegation and delegates
- `property_delegate` — property delegate `by expr` (children: _expression)
- `explicit_delegation` — delegation in inheritance `Type by expr`
- `constructor_delegation_call` — `this(...)` or `super(...)` in a constructor

### Import and package
- `package_header` — package declaration (children: `package` keyword, qualified_identifier)
- `import` — one import statement (children: `import` keyword, qualified_identifier; a wildcard `import p.*` appends trailing anonymous `.` and `*` siblings; an alias appends `as` + identifier — there is no dedicated alias or wildcard node)

### Getter/Setter
- `getter` — property getter (children: modifiers, function_body)
- `setter` — property setter (children: modifiers, parameter_with_optional_type, function_body)

## Signature extraction

AST traversal — `node.children` + checking `node.type`.
Node text — `node.text.decode('utf-8')`.
Children by field name — `node.child_by_field_name(field)`.

**IMPORTANT**: most Kotlin AST nodes do not have named fields. Children are accessible positionally via `node.children`.
Named fields only exist for: `function_declaration.receiver`, `property_declaration.receiver`, `function_type.receiver`,
`if_expression.condition/consequence/alternative`.

### Pattern: extracting function parameters
```python
def _extract_params(params_node):
    if params_node is None or params_node.type != "function_value_parameters":
        return ""
    parts = []
    for child in params_node.children:
        if child.type == "parameter":
            name_node = child.child_by_field_name("name")
            if name_node is None:
                for ch in child.children:
                    if ch.type == "identifier":
                        name_node = ch
                        break
            if name_node:
                parts.append(name_node.text.decode("utf-8"))
    return ", ".join(parts)
```

### Pattern: traversing top-level declarations
```python
for node in root.children:
    if node.type == "function_declaration":
        name = _first_child_by_type(node, "identifier")
        params = _first_child_by_type(node, "function_value_parameters")
        # extension function?
        receiver = node.child_by_field_name("receiver")
    elif node.type == "class_declaration":
        name = _first_child_by_type(node, "identifier")
        body = _first_child_by_type(node, "class_body")
        # check modifiers for data/sealed/annotation/inner/value
    elif node.type == "property_declaration":
        binding = _first_child_by_type(node, "binding_pattern_kind")  # val/var
        var_decl = _first_child_by_type(node, "variable_declaration")
    elif node.type == "object_declaration":
        name = _first_child_by_type(node, "identifier")
    elif node.type == "type_alias":
        name = _first_child_by_type(node, "identifier")


def _first_child_by_type(node, type_name):
    for child in node.children:
        if child.type == type_name:
            return child
    return None
```

### Pattern: extracting class methods and properties
```python
def _extract_class_members(class_body_node):
    methods = []
    properties = []
    for child in class_body_node.children:
        if child.type == "function_declaration":
            name = _first_child_by_type(child, "identifier")
            params = _first_child_by_type(child, "function_value_parameters")
            if name:
                methods.append(name.text.decode("utf-8"))
        elif child.type == "property_declaration":
            var_decl = _first_child_by_type(child, "variable_declaration")
            if var_decl:
                ident = _first_child_by_type(var_decl, "identifier")
                if ident:
                    properties.append(ident.text.decode("utf-8"))
    return methods, properties
```

### Pattern: determining class kind (data/sealed/enum/annotation/interface)
```python
def _class_kind(class_decl_node):
    has_enum_body = any(c.type == "enum_class_body" for c in class_decl_node.children)
    if has_enum_body:
        return "enum"

    for child in class_decl_node.children:
        if child.type == "modifiers":
            for mod in child.children:
                if mod.type == "class_modifier":
                    return mod.text.decode("utf-8")  # "data", "sealed", "annotation", "inner", "value"
        # check for "interface" among anonymous tokens
        if child.type == "fun":
            return "fun_interface"

    return "class"
```

### Pattern: finding companion object
```python
def _find_companion(class_body_node):
    for child in class_body_node.children:
        if child.type == "companion_object":
            return child
    return None
```
