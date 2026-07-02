---
name: goga-cell-python
description: Python rules for implementing CODEMANIFEST contracts
---
# Python: Contract Implementation Rules

Language skill for Python.

Apply the specification within the context of the invoking skill. Do not paraphrase the content — use it
for decision-making.

Invoke via the `goga-lang-disp` router.

---

## Examples

Full CODEMANIFEST example for Python with all DSL constructs:

```yaml
Imports:
  - Types:
      - DataModel
      - BaseConfig AS Config
    Usages:
      - serialization
    From: path/to/data_cell

Usages:
  conventions: .goga/usages/python_conventions.md
  pattern: |
    All public methods must use type hints. Return values are immutable where possible.
  testing: |
    Each routine and entity method must have a corresponding test in tests/.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `serialization` from Imports for data encoding patterns.

  All methods must return concrete types, not `Any`.

---

"parse_input(input: str) -> data: bytes":
  location: parser.py
  annotations: |
    Parse raw input string into structured data.

    `input`: raw string to parse

    Use `pattern` for implementation.

"DataProcessor(config: Config)":
  location: processor.py
  annotations: |
    Process data according to configuration.

    `config`: processor configuration from `Config` type.

    Use `serialization` from Imports for encoding.
    Use `conventions` for code style.
  properties:
    "name -> str": |
      Processor identifier.
    "buffer_size -> int": |
      Maximum buffer size in bytes.
  methods:
    "process(data: list[T]) -> result: list[T]": |
      Process a batch of data items.

      `data`: input items to process
      `result`: processed items

      Use `pattern` for implementation.
    "reset()": |
      Reset internal state.

"BaseHandler::HTTPHandler(host: str)":
  location: handler.py
  annotations: |
    HTTP-specific handler extending BaseHandler.

    `host`: server hostname

    Use `serialization` from Imports for request/response encoding.

->DataModel: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for Python.
```

## Cell

A cell is a Python package:

```
cell/
├── CODEMANIFEST
├── __init__.py
```

## Language Specifics

**Facade**: `__init__.py` must expose the full contract API through `__all__`. Only identifiers listed in
`__all__` constitute the cell facade.

**Naming**: PascalCase for classes; snake_case for functions, methods, and properties.

**Constructors**: The entity signature describes `__init__` (the `self` parameter is excluded from the contract).

**Type hints**: mandatory. Type annotations drive signature extraction for properties and methods.

## Construct Mapping

| Python                             | CODEMANIFEST     | Note                                       |
|------------------------------------|------------------|--------------------------------------------|
| `class` in `__all__`               | Entity           | Class exported through `__all__`           |
| `def` at module level in `__all__` | Routine          | Function exported through `__all__`        |
| `@property` in class               | Property         | Type extracted from return annotation      |
| `def` method in class              | Method           | `self` excluded from signature             |
| `__init__` parameters              | Entity signature | `self` excluded                            |

## Implementation

- Public API must be importable from package root
- Use classes and functions
- Type hints are mandatory

## Signature Rules

Allowed:
```
str, int, float, bool,
list[T], dict[str, T],
T | None
```

Forbidden:
```
*args, **kwargs,
dict without generics,
list without generics
```

## Arbitrary arguments

```yaml
"dynamic_signature(...args: str, ...kwargs: dict) -> value:str":
  annotations: |
    Dynamic parameters example

    `args`: non-keyword, positional arguments (*args)
    `kwargs`: keyword, named arguments (**kwargs)
```

---
