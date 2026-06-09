# Language Support

goga extracts contracts from source code using **tree-sitter** parsers. A contract is a machine-readable description of the public API surface of a cell -- its entities (classes, structs, interfaces), routines (functions), properties, and method signatures.

## Supported Languages

| Language | Parser | Function |
|---|---|---|
| [Python](python.md) | tree-sitter-python | `python_contract(cell_path)` |
| [Go](golang.md) | tree-sitter-go | `golang_contract(cell_path)` |
| [Kotlin](kotlin.md) | tree-sitter-kotlin | `kotlin_contract(cell_path)` |
| [Swift](swift.md) | tree-sitter-swift | `swift_contract(cell_path)` |
| [JavaScript](javascript.md) | tree-sitter-javascript | `javascript_contract(cell_path)` |

## Dispatching

All language extractors share a single entry point:

```python
from goga.contract import contract

results = contract("python", "path/to/cell")
```

The `contract(lang, cell_path)` function accepts a language identifier string (`python`, `golang`, `javascript`, `kotlin`, `swift`) and dispatches to the corresponding parser. It raises `ValueError` for unsupported languages.

## Output

Every extractor returns the same type:

```python
list[EntityContract | RoutineContract]
```

- **EntityContract** -- a class, struct, interface, or protocol with its public properties and methods
- **RoutineContract** -- a top-level function with its parameter and return type signature

Each contract item carries a `name`, `signature`, and a computed `contract` field (e.g. `MyClass(name: str)`). Results are sorted alphabetically by name, with entity internals (properties, methods) also sorted.

## Architecture

All extractors follow the same pattern:

1. Scan the cell directory for source files matching the language extension
2. Parse each file with the language-specific tree-sitter grammar
3. Walk the AST and collect public definitions (classes become entities, functions become routines)
4. Merge results from multiple files into a single deduplicated list
5. Sort and return

Shared utilities live in `goga/contract/treesitter_utils.py`, and the data model is defined in `goga/contract/data/contract.py`.
