# tree-sitter + tree-sitter-go

## Purpose
Python bindings for incremental parsing. tree-sitter-go is a Go grammar.

## Installation
pip install tree-sitter tree-sitter-go

## Basic pattern for parsing a Go file

```python
import tree_sitter_go as tsgo
from tree_sitter import Language, Parser

GO_LANG = Language(tsgo.language())

parser = Parser(GO_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node
```

## Key Go AST node types

### Declarations
- `function_declaration` — function (fields: name, parameters, result)
- `method_declaration` — method with a receiver (fields: receiver, name, parameters, result)
- `type_declaration` — type declaration container (children: type_spec)

### Type declarations
- `type_spec` — type specification inside a type_declaration (fields: name, type)
- `struct_type` — struct (children: field_declaration_list)
- `interface_type` — interface (children: method_elem)

### Fields and parameters
- `field_declaration_list` — struct field list (children: field_declaration)
- `field_declaration` — struct field (fields: name, type)
- `parameter_list` — parameter list (children: parameter_declaration, variadic_parameter_declaration)
- `parameter_declaration` — parameter (fields: name, type)
- `variadic_parameter_declaration` — variadic parameter (fields: name, type)

### Interface methods
- `method_elem` — interface method inside an interface_type (fields: name, parameters, result)

### Names
- `identifier` — identifier (variable name, parameter)
- `field_identifier` — field/method name (in a receiver, struct)
- `type_identifier` — type name

## Signature extraction

AST traversal — `node.children` + check `node.type`.
Node text — `node.text.decode('utf-8')`.
Children by field name — `node.child_by_field_name(field)`.

### Available node fields (field names)
- `name` — declaration name (function, method, type, field)
- `type` — type (of parameter, field, receiver)
- `parameters` — function/method parameter list
- `result` — function/method return value
- `receiver` — method receiver (for method_declaration)
