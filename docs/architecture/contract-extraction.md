# Contract Extraction

The contract extraction system parses source code files to discover what entities and routines are actually implemented. This information is compared against CODEMANIFEST declarations to verify completeness.

## Entry Point

```python
contract(language: str, cell_path: str) -> list[EntityContract | RoutineContract]
```

- `language` -- the programming language of the source code, used to dispatch to the correct parser.
- `cell_path` -- the file or directory path containing the source code.
- Returns a list of `EntityContract` and `RoutineContract` instances representing what the code implements.

The language parameter is resolved from the project configuration. Based on its value, the system selects the appropriate tree-sitter parser.

## Data Structures

### BaseContract

Abstract base for all extracted contracts.

| Property | Type | Description |
|---|---|---|
| `name` | `str` | The name of the entity or routine. |
| `signature` | `str` | The type signature as declared in code. |
| `contract` | `str` | The contract identifier linking to the CODEMANIFEST declaration. |

### EntityContract

Represents a class, struct, or interface extracted from source code.

| Property | Type | Description |
|---|---|---|
| `properties` | `list[PropertyContract]` | Properties of the entity. |
| `methods` | `list[MethodContract]` | Methods of the entity. |

Inherits `name`, `signature`, and `contract` from `BaseContract`.

### PropertyContract

A property belonging to an entity.

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Property name. |
| `signature` | `str` | Property type signature. |

### MethodContract

A method belonging to an entity.

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Method name. |
| `signature` | `str` | Method signature including parameters and return type. |

### RoutineContract

Represents a standalone function (not belonging to any entity).

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Function name. |
| `signature` | `str` | Function signature. |
| `contract` | `str` | Contract identifier. |

## Supported Languages

Each language uses a dedicated tree-sitter grammar to parse source code into an AST, then walks the AST to extract contract information.

### Python (tree-sitter-python)

Extracts:

- Classes with their methods, properties, and decorators.
- Standalone functions.
- Method signatures including parameter lists and return annotations.

### Go (tree-sitter-go)

Extracts:

- Structs and interfaces.
- Functions and methods (including receiver functions).
- Struct fields as properties.

### Kotlin (tree-sitter-kotlin)

Extracts:

- Classes and data classes.
- Functions and extension functions.
- Properties with their type annotations.

### Swift (tree-sitter-swift)

Extracts:

- Classes, structs, and protocols.
- Functions and methods.
- Properties with access level and type.

### JavaScript (tree-sitter-js)

Extracts:

- Classes with methods.
- Functions and arrow functions.
- Class properties.

## Extraction Process

For each supported language, the extraction follows the same pattern:

1. **Read source files** -- load all relevant source files from `cell_path`.
2. **Parse with tree-sitter** -- build a syntax tree using the language-specific grammar.
3. **Walk the tree** -- traverse the AST looking for declarations (classes, functions, methods, properties).
4. **Build contracts** -- for each declaration, create the corresponding contract object with name, signature, and nested members.
5. **Return results** -- collect all contracts into a flat list.

The extracted contracts are then compared against the CODEMANIFEST declarations to identify missing implementations or undeclared code.

## Where to Next

- [AST Factory](ast-factory.md) -- how CODEMANIFEST declarations are parsed.
- [Validation Rules](validation-rules.md) -- rules that validate contract declarations.
- [Architecture Overview](index.md) -- the full pipeline context.
