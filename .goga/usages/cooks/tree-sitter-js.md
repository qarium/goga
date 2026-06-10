# tree-sitter + tree-sitter-javascript

## Purpose
Python bindings for incremental parsing. tree-sitter-javascript is a JavaScript grammar.

## Installation
pip install tree-sitter tree-sitter-javascript

## Basic pattern for parsing a JavaScript file

```python
import tree_sitter_javascript as tsjs
from tree_sitter import Language, Parser

JS_LANG = Language(tsjs.language())

parser = Parser(JS_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node
```

## Key JavaScript AST node types

### Declarations
- `function_declaration` — function (fields: name, parameters, body)
- `class_declaration` — class (fields: name, body, decorator; children: class_heritage)
- `generator_function_declaration` — generator function (fields: name, parameters, body)
- `lexical_declaration` — let/const declaration (children: variable_declarator)
- `variable_declaration` — var declaration (children: variable_declarator)

### Exports (ESM)
- `export_statement` — export (fields: declaration, source, value; children: export_clause, namespace_export)
  - `export function Foo() {}` → declaration → function_declaration
  - `export class Bar {}` → declaration → class_declaration
  - `export { a, b }` → children → export_clause → export_specifier
  - `export default expr` → value → expression
  - `export * from 'mod'` → source → string, children → namespace_export

### Class
- `class_body` — class body (field: member → field_definition | method_definition | class_static_block)
- `method_definition` — class method (fields: name, parameters, body, decorator)
- `field_definition` — class field (fields: property, value, decorator)

### Function
- `formal_parameters` — parameter list (children: assignment_pattern | pattern)
- `identifier` — variable/parameter name
- `assignment_pattern` — parameter with default value (fields: left, right)

### CommonJS
- `expression_statement` → `assignment_expression` — for `module.exports = ...`
  - `assignment_expression` (fields: left, right)
  - left → `member_expression` (module.exports)
  - right → `object` (with methods/properties) or `identifier` (function name)

### Names
- `identifier` — regular identifier
- `property_identifier` — property/method name
- `private_property_identifier` — private property (#field)

### Comments
- `comment` — comment node (extra node, accessible via traversal)
- JSDoc: `/** @param {string} name - description */` — parsed as a comment, types are extracted via text analysis

## Extracting signatures

AST traversal — `node.children` + checking `node.type`.
Node text — `node.text.decode('utf-8')`.
Children by field name — `node.child_by_field_name('name')`.

### Pattern: extracting function parameters
```python
def _extract_params(params_node):
    if params_node is None or params_node.type != "formal_parameters":
        return ""
    parts = []
    for child in params_node.children:
        if child.type == "identifier":
            parts.append(child.text.decode("utf-8"))
        elif child.type == "assignment_pattern":
            left = child.child_by_field_name("left")
            if left:
                parts.append(left.text.decode("utf-8"))
    return ", ".join(parts)
```

### Pattern: finding exports
```python
for node in root.children:
    if node.type == "export_statement":
        decl = node.child_by_field_name("declaration")
        if decl and decl.type == "function_declaration":
            # processing exported function
            pass
        elif decl and decl.type == "class_declaration":
            # processing exported class
            pass
```

### Pattern: extracting class methods
```python
def _extract_class_methods(class_body_node):
    methods = []
    for member in class_body_node.children_by_field_name("member"):
        if member.type == "method_definition":
            name_node = member.child_by_field_name("name")
            params_node = member.child_by_field_name("parameters")
            # ...
    return methods
```
