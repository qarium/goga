---
name: goga-cell-swift
description: Swift CODEMANIFEST contract implementation rules
---
# Swift: Contract Implementation Rules

Language skill for Swift.

Apply the specification within the context of the calling skill. Do not restate the content — use it
for decision-making.

Invoked via the `goga-lang-disp` router.

---

## Examples

Complete CODEMANIFEST example for Swift covering all DSL constructs:

```yaml
Imports:
  - Types:
      - NetworkService
      - SessionConfig AS Config
    Usages:
      - authentication
    From: path/to/network_cell

Usages:
  conventions: .goga/usages/swift_conventions.md
  pattern: |
    Use value types (struct) by default. Use reference types (class) only when identity or shared mutation is required.
  testing: |
    Use XCTest. Each public method must have test coverage.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `authentication` from Imports for auth token handling.

  Prefer `struct` over `class` unless reference semantics are needed.

---

"parseInput(input: String) -> data: Data":
  location: Parser.swift
  annotations: |
    Parse raw input string into structured data.

    `input`: raw string to parse

    Use `pattern` for implementation.

"NetworkManager(baseURL: String)":
  location: NetworkManager.swift
  annotations: |
    Network client for API communication.

    `baseURL`: root URL for all API requests

    Use `authentication` from Imports for request signing.
    Use `conventions` for code style.
  properties:
    "baseURL -> String": |
      Root URL for API requests.
    "isConnected -> Bool": |
      Current connection status.
  methods:
    "fetchData(endpoint: String) -> response: Promise<Data>": |
      Fetch data from the specified endpoint.

      `endpoint`: API endpoint path
      `response`: async response data

      Use `pattern` for implementation.
    "cancelPendingRequests()": |
      Cancel all in-flight requests.

"NetworkService::AuthenticatedService(token: String)":
  location: AuthService.swift
  annotations: |
    Authenticated service extending NetworkService with token-based auth.

    `token`: authentication token

    Use `authentication` from Imports for token refresh logic.

->NetworkService: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for Swift.
```

## Cell

A cell is a module:

```
cell/
├── CODEMANIFEST
├── *.swift
```

## Language Features

**Facade**: only declarations with the `public` access modifier constitute the Facade. `internal` (the default access level) and `private` declarations are excluded from the Contract.

**Naming**: camelCase for functions and properties, PascalCase for types.

**Value types**: `struct` defines a Value Type, `class` defines a Reference Type. Select based on entity Semantics.

**Optionals**: `T?` denotes an Optional. Represent as `T?` in CODEMANIFEST.

**Protocol**: protocols define interfaces — map to Entity with methods only, excluding properties.

## Construct Mapping

| Swift                            | CODEMANIFEST     | Note                              |
|----------------------------------|------------------|-----------------------------------|
| `public class` / `public struct` | Entity           | Init parameters → Entity Signature |
| `public func` (top-level)        | Routine          |                                   |
| `public var` / `public let`      | Property         | Type from declaration             |
| `public func` (method)           | Method           |                                   |
| `public protocol`                | Entity           | Methods only, no properties       |
| `init` parameters                | Entity Signature |                                   |

## Implementation

- Public API must use `public`
- Use class/struct depending on semantics

## Signature Rules

Allowed:
```
String, Int, Double, Bool
[T]
[String: T]
T?
```

Forbidden:
```
Any
UnsafePointer
inout
```

---
