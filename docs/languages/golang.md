# Go Contract Extraction

## Overview

The Go extractor scans a package directory for `.go` files (excluding `_test.go`) and uses **tree-sitter-go** to parse them. It identifies structs, interfaces, functions, and methods, extracting only exported symbols.

## API

```python
from goga.contract.golang import golang_contract

contracts = golang_contract("path/to/package")
# Returns list[EntityContract | RoutineContract]
```

`golang_contract` accepts a path to a Go package directory. Returns an empty list if no `.go` files are found.

## What Gets Extracted

| Source Construct | Contract Type | Notes |
|---|---|---|
| `type X struct {}` | `EntityContract` | Exported struct fields become properties |
| `type X interface {}` | `EntityContract` | Interface methods are collected |
| `func X()` | `RoutineContract` | Exported top-level functions |
| `func (r *X) M()` | `MethodContract` | Methods attached to their receiver struct |

### Visibility Rules

- Only exported (uppercase) names are included
- Unexported struct fields are excluded
- Unexported methods are excluded
- Methods are attached to struct entities only (not interfaces)
- `_test.go` files are skipped

## Key Node Types

The parser walks these tree-sitter node types:

- `type_declaration` -- struct and interface declarations
- `function_declaration` -- top-level function declarations
- `method_declaration` -- method declarations with receivers
- `interface_type` -- interface method sets
- `struct_type` -- struct field lists

## Example

Given a Go package with two files:

```go
// model.go
package cell

type Server struct {
    Name string
    Port int
}
```

```go
// methods.go
package cell

func (s *Server) Start() error { return nil }
func (s *Server) Stop()        {}
func Hello(name string) string  { return "Hello " + name }
```

The extracted contracts are:

| Name | Type | Signature |
|---|---|---|
| `Server` | EntityContract | `()` |
| `Hello` | RoutineContract | `(name: string) -> string` |

`Server` has two properties (`Name: string`, `Port: int`) and two methods (`Start() -> error`, `Stop()`).
