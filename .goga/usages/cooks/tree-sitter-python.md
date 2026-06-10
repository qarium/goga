# tree-sitter + tree-sitter-python

## Purpose
Python bindings for incremental parsing. tree-sitter-python is the Python grammar.

## Installation
pip install tree-sitter tree-sitter-python

## Basic pattern for parsing a Python file

```python
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANG = Language(tspython.language())

parser = Parser(PY_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node
```

## Key Python AST node types

### Declarations
- `function_definition` — function (fields: name, parameters, return_type)
- `class_definition` — class (fields: name, superclasses, body)
- `decorated_definition` — decorated declaration (children: decorator + function/class_definition)

### Parameters
- `parameters` — parameter list (children: identifier, typed_parameter, default_parameter, typed_default_parameter, list_parameter_pattern, dictionary_parameter_pattern)
- `typed_parameter` — parameter with a type annotation (fields: name, type)
- `default_parameter` — parameter with a default value (fields: name, value)
- `typed_default_parameter` — parameter with a type annotation and a default value (fields: name, type, value)
- `list_parameter_pattern` — *args (fields: name)
- `dictionary_parameter_pattern` — **kwargs (fields: name)

### Assignments
- `assignment` — assignment (fields: left, right)
- `expression_statement` — expression statement (for __all__ = [...])

### Type annotations
- `type` — type annotation (children: various type nodes)
- `identifier` — identifier
- `string` — string literal (for from __future__ import annotations)

### Properties and methods
- `decorator` — decorator (for @property)
- `function_definition` inside a class body — method

## Signature extraction

AST traversal — `node.children` + checking `node.type`.
Node text — `node.text.decode('utf-8')`.
Children by field name — `node.child_by_field_name(field)`.

### Available node fields (field names)
- `name` — declaration name (of a function, class, or parameter)
- `type` — type (of a parameter or return)
- `parameters` — parameter list of a function/method
- `return_type` — return type of a function/method
- `body` — body of a function/class
- `superclasses` — base classes
- `left` / `right` — left/right side of an assignment
- `value` — value (for default_parameter)
