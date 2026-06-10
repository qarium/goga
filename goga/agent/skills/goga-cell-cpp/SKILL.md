---
name: goga-cell-cpp
description: C++ CODEMANIFEST contract implementation rules
---
# C++: Contract Implementation Rules

Language skill for C++.

Apply the specification in the context of the calling skill. Do not retell the content — use it
for decision-making.

Invoked through the `goga-lang-disp` router.

---

## Examples

Full CODEMANIFEST example for C++ with all DSL constructs:

```yaml
Imports:
  - Types:
      - Buffer
      - StreamConfig AS Config
    Usages:
      - memory_layout
    From: path/to/stream_cell

Usages:
  conventions: .goga/usages/cpp_conventions.md
  pattern: |
    Use RAII for resource management. Prefer stack allocation over heap allocation.
  testing: |
    Use Catch2. Each public function must have test coverage.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `memory_layout` from Imports for buffer alignment rules.

  Use value semantics only. No raw pointers or references in public API.

---

"lookup_entry(std::string key) -> value: int":
  location: engine.hpp
  annotations: |
    Look up an entry by key.

    `key`: lookup key string
    `value`: found value or 0 if not found

    Use `pattern` for implementation.

"Parser(input: std::string)":
  location: parser.hpp
  annotations: |
    Configurable parser for structured input.

    `input`: raw input string

    Use `memory_layout` from Imports for buffer sizing.
    Use `conventions` for code style.
  properties:
    "position -> int": |
      Current parsing position.
    "length -> int": |
      Total input length.
  methods:
    "parse() -> tokens: std::vector<std::string>": |
      Parse input into tokens.

      `tokens`: parsed token list

      Use `pattern` for implementation.
    "reset()": |
      Reset parser state to beginning.

"Buffer::StreamBuffer(config: Config)":
  location: stream.hpp
  annotations: |
    Stream buffer extending Buffer with configurable capacity.

    `config`: buffer configuration from `Config` type.

    Use `memory_layout` from Imports for allocation strategy.

->Buffer: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for C++.
```

## Cell

A cell is a directory with a public header:

```
cell/
├── CODEMANIFEST
├── cell.hpp
```

## Language Features

**Facade**: the header file (`cell.hpp`) defines the public API. Everything declared in the header within the cell namespace
constitutes the facade. Implementation resides in the corresponding `.cpp` files.

**Naming**: PascalCase for user-defined classes and structs, snake_case for functions and variables.
Standard library types (`std::string`, `std::vector`) are used as-is (snake_case).

**Namespace**: each cell uses its own namespace for isolation.

**Constructors**: the Entity signature describes the class constructor. Constructor parameters are the input data.

**Memory**: pointers, references, and smart pointers are forbidden in the contract. Use value semantics.

## Construct Mapping

| C++                            | CODEMANIFEST     | Note                          |
|--------------------------------|------------------|-------------------------------|
| `class` / `struct` in namespace | Entity           | Constructor → Entity signature |
| Free function in namespace     | Routine          |                               |
| Public member variable         | Property         |                               |
| Public member function         | Method           |                               |
| Constructor                    | Entity signature |                               |

## Implementation

- Public API defined in header
- Use namespace per cell

## Signature Rules

Allowed:
```
std::string
int, double, bool
std::vector<T>
std::map<K, V>
std::optional<T>
```

Forbidden:
```
pointers (*T)
references (&, &&)
smart pointers
void*
templates in DSL
```

---
