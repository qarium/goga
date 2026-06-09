# Swift Contract Extraction

## Overview

The Swift extractor scans a package directory for `.swift` files and uses **tree-sitter-swift** to parse them. It identifies classes, structs, enums, protocols, actors, and free functions, extracting only `public` and `open` declarations.

## API

```python
from goga.contract.swift import swift_contract

contracts = swift_contract("path/to/package")
# Returns list[EntityContract | RoutineContract]
```

`swift_contract` accepts a path to a Swift package directory. Returns an empty list if no `.swift` files are found.

## What Gets Extracted

| Source Construct | Contract Type | Notes |
|---|---|---|
| `public class X { ... }` | `EntityContract` | Init params form signature |
| `public struct X { ... }` | `EntityContract` | Same handling as class |
| `public actor X { ... }` | `EntityContract` | Same handling as class |
| `public enum X { ... }` | `EntityContract` | Enum cases become properties |
| `public protocol X { ... }` | `EntityContract` | Protocol method requirements collected |
| `public func x() -> T` | `RoutineContract` | Top-level public functions |

### Visibility Rules

- Only `public` and `open` declarations are included
- `internal` (default) and `private` declarations are excluded
- Extensions are skipped entirely
- Non-public initializers are ignored (entity signature falls back to `()`)

## Key Node Types

The parser walks these tree-sitter node types:

- `class_declaration` -- class, struct, actor, and enum declarations (distinguished by `declaration_kind`)
- `protocol_declaration` -- protocol declarations
- `function_declaration` -- free functions and type member functions
- `property_declaration` -- stored and computed properties
- `init_declaration` -- designated and failable initializers
- `enum_entry` -- enum cases

## Example

Given a Swift file `Server.swift`:

```swift
public class Server {
    public init(host: String, port: Int) {}
    public func start() -> Bool { return true }
    public var name: String = ""
}

public func greet(name: String) -> String {
    return name
}
```

The extracted contracts are:

| Name | Type | Signature |
|---|---|---|
| `Server` | EntityContract | `(host: String, port: Int)` |
| `greet` | RoutineContract | `(name: String) -> String` |

`Server` has one property (`name: String`) and one method (`start() -> Bool`).

### External Parameter Names

Swift's external parameter names are preserved in signatures:

```swift
public func configure(with host: String, port: Int) {}
```

Extracted signature: `(with host: String, port: Int)`
