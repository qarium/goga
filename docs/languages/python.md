# Python Contract Extraction

## Overview

The Python extractor scans a package directory for `.py` files and uses **tree-sitter-python** to parse them. It identifies classes and functions defined at the module level, then extracts their public API surface.

## API

```python
from goga.contract.python import python_contract

contracts = python_contract("path/to/package")
# Returns list[EntityContract | RoutineContract]
```

`python_contract` accepts a path to a Python package directory (containing `.py` files). It raises `FileNotFoundError` if the path does not exist.

## What Gets Extracted

| Source Construct | Contract Type | Notes |
|---|---|---|
| `class MyClass:` | `EntityContract` | Signature derived from `__init__` params |
| `def my_func():` | `RoutineContract` | Top-level functions only |
| `@property` methods | `PropertyContract` | Return type used as property signature |
| `@staticmethod` / `@classmethod` | `MethodContract` | Treated as class methods |
| Type-annotated class fields (PEP 526) | `PropertyContract` | `name: str` style declarations |

### Visibility Rules

- Names starting with `_` are excluded (private convention)
- `self` and `cls` parameters are stripped from method signatures
- Non-callable module-level assignments (e.g. `VALUE = 42`) are ignored

## Key Node Types

The parser walks these tree-sitter node types:

- `class_definition` -- class declarations
- `function_definition` -- function and method declarations
- `decorated_definition` -- methods with decorators (`@property`, `@staticmethod`, etc.)
- `assignment` -- type-annotated field declarations inside class bodies

## Example

Given a package with `__init__.py`:

```python
class Service:
    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def info(self) -> str:
        return self.name

    def run(self, task: str) -> bool:
        return True

    def _internal(self) -> None:
        pass


def connect(host: str, port: int = 8080) -> None:
    pass
```

The extracted contracts are:

| Name | Type | Signature |
|---|---|---|
| `Service` | EntityContract | `(name: str)` |
| `connect` | RoutineContract | `(host: str, port: int = 8080) -> None` |

`Service` has one property (`info: str`) and one method (`run(task: str) -> bool`). The `_internal` method is excluded.
