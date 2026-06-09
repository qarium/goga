---
name: goga-cell-go
description: Golang rules for implementing CODEMANIFEST contracts
---
# Golang: Contract Implementation Rules

Language skill for Golang.

Apply this specification within the calling skill's context. Do not paraphrase the contents — use them
to drive decisions.

Invoked through the `goga-lang-disp` router.

---

## Examples

A complete CODEMANIFEST example for Go with all DSL constructs:

```yaml
Imports:
  - Types:
      - BaseModel
      - RepositoryConfig AS Config
    Usages:
      - query_patterns
    From: path/to/storage_cell

Usages:
  conventions: .goga/usages/go_conventions.md
  pattern: |
    Follow Go idioms: return errors as last return value, use interfaces for abstraction.
  testing: |
    Table-driven tests required for all exported functions and methods.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `query_patterns` from Imports for database query patterns.

  All methods returning errors must follow `(result, error)` pattern.

---

"ParseInput(input string) -> data:[]byte":
  location: parser.go
  annotations: |
    Parse raw input string into structured data.

    `input`: raw string to parse

    Use `pattern` for implementation.

"Server(host string)":
  location: server.go
  annotations: |
    HTTP server with configurable host.

    `host`: server hostname

    Use `query_patterns` from Imports for request handling.
    Use `conventions` for code style.
  properties:
    "Host -> string": |
      Server hostname.
    "Port -> int64": |
      Server port number.
  methods:
    "HandleRequest(req Request) -> resp:Response, err:error": |
      Handle incoming HTTP request.

      `req`: incoming request
      `resp`: response to send
      `err`: error if request handling fails

      Use `pattern` for implementation.
    "Shutdown() -> err:error": |
      Gracefully shut down the server.
      `err`: error if shutdown fails.

"BaseModel::Repository(db DB)":
  location: repository.go
  annotations: |
    Repository extending BaseModel with database operations.

    `db`: database connection

    Use `query_patterns` from Imports for query construction.

->BaseModel: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for Go.
```

## Cell

A cell is a Go package:

```
cell/
├── CODEMANIFEST
├── cell.go
```

## Language Specifics

**Facade**: The Go package itself serves as the facade. All exported identifiers define the cell's public API.
The contract-extractor reads exported names verbatim — names declared in CODEMANIFEST must match exactly.

**Naming**: Use camelCase for all identifiers (no underscores). Exported identifiers start with
an uppercase letter: `SomeFunc`, `SomeField`. Unexported identifiers start with lowercase: `someFunc`, `someField`.
CODEMANIFEST references exported names only.

**Constructors**: Go does not provide constructors. The Entity signature declares a factory function (e.g. `NewServer()`).

**Methods**: Methods are defined via receivers, not inside struct definitions. The contract-extractor associates methods
with their struct based on the receiver type.

**Error handling**: Follow the `(result, error)` idiom. CODEMANIFEST return values must carry
a semantic label: `() -> err:error` or `() -> result:T, err:error`.

## Construct Mapping

| Go                              | CODEMANIFEST     | Note                                      |
|---------------------------------|------------------|-------------------------------------------|
| `type X struct`                 | Entity           | Struct fields → properties (exported only)|
| `type X interface`              | Entity           | Interface methods → methods               |
| `func (r *X) Method()`          | Method           | Bound to Entity by receiver type          |
| `func Name()` (no receiver)     | Routine          | Package-level function                    |
| Exported struct field           | Property         | Type derived from field declaration       |

## Implementation

- Public API = exported identifiers
- Use structs + functions

## Signature Rules

Allowed:
```
string, int, float64, bool, error
[]T, map[string]T
```

Forbidden:
```
pointers (*T),
interface{},
variadic (...),
channels,
```

---
