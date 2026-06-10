# CODEMANIFEST

The CODEMANIFEST file is a YAML DSL document that defines a **cell contract** — a language-agnostic set of types and their expected API. The document does not prescribe *how* to implement the code. It specifies **the API and behavioral expectations** that the implementation must satisfy.

YAML key casing is **case-sensitive**: keys must appear in the exact casing shown in this specification.

## Document structure

The document consists of three logical sections separated by the YAML document marker `---`:

1. **Header** — establishes context: type sources (`Imports`), practices (`Usages`), global directives (`Annotations`)
2. **Body** — type declarations and their expected behavior
3. **Footer** — metadata that does not affect the contract architecture: `Author`, `CreatedAt`, `Description`

The section order is **mandatory**: Header → Body → Footer.

### Complete example

```yaml
Imports:
  - Types:
      - AnotherCellType
    Usages:
      - another_cell_usage
    From: path/to/another_cell

Usages:
  conventions: .goga/usages/conventions.md
  pattern: |
    Some pattern here
  testing: |
    Requirements to tests

Annotations: |
  Use `conventions` for write code.
  Use `testing` for write tests.
  Use `another_cell_usage` from Imports for additional context.

---

"ParseInput(input: string) -> data:List<byte>":
  location: parser.py
  annotations: |
    Description of routine.

    `input`: description of input

    Use `pattern` for implementation

"HTTPServer(name: String)":
  location: server.py
  annotations: |
    Description of entity.
    Use `pattern` for implementation
    Use `AnotherCellType` from Imports for data types
  properties:
    "host -> String": |
      Description of property
  methods:
    "handleRequest(req: Request) -> resp:Response": |
      Description of method.
      `req`: description of req
      Use `pattern` for implementation

---

Author: FirstName LastName
CreatedAt: 01/01/26
Description: |
  Description of CODEMANIFEST file
```

## Header

The Header defines the interpretation context for the entire file.

### Imports

Imports bring types and practices from other cells into the current contract.

```yaml
Imports:
  - Types:
      - ObjectOne
      - ObjectTwo AS Object
    Usages:
      - example_one       # path/to/cell/.usages/example_one.md
      - example_two AS example  # aliased import
    From: path/to/cell
```

- `Types` — list of type names to import
- `Usages` — list of practice names to import (with optional `AS` alias)
- `From` — source path (directory relative to the working directory containing the `CODEMANIFEST` file)
- The `ObjectTwo AS Object` syntax imports `ObjectTwo` under the alias `Object`

**When to import Types:**

- The current contract requires a type defined in another cell (in a signature, argument, or return value)
- You need to mutate or embed a type from another cell

**When to import Usages:**

- You need to reference a practice from another cell within annotations

Imported types may:

- Appear in declared interfaces
- Undergo mutation and extension
- Be embedded into the current contract

Restrictions:

- Cross-imports between cells are prohibited: cell A cannot import from cell B if cell B imports from cell A
- Imported practices must not conflict with local `Usages` keys (use `AS` alias to resolve)

### Usages directive

The `Usages` header directive declares a named set of practices for reference in annotations. Each key serves as the practice identifier for backtick references in annotations.

```yaml
Usages:
  library: .goga/usages/encoding.md
  structures: https://goga.example/structures.md
  pattern: |
    Inline usage description here...
```

Values accept:

- A path to an `.md` file relative to the project root (must reside in `.goga/usages/`)
- A URL
- An inline description

**When to declare a practice:**

- An external library or tool exists that the agent must account for during implementation
- A pattern or convention applies to the contract's types
- A data structure or format recurs across multiple locations

Every connected practice must be referenced in at least one annotation — global, type-level, method-level, or property-level.

### Annotations (global)

Global directives addressed to the implementing agent, applying to the entire document.

```yaml
Annotations: |
  Use `conventions` for write code.
  Use `testing` for write tests.
```

They convey:

- Implementation requirements
- Constraints
- Architectural expectations
- Practice application hints

**When to write global annotations:**

- Requirements apply to all types in the cell (e.g., a library, error style, logging)
- You need to prioritize between conflicting practices from Usages

## Body

The body defines **contract types** — which API elements must exist and how they must behave. Three constructs are available: type declaration, type mutation, and type embedding.

### Entity type

An Entity has `methods` and/or `properties`. It represents a type that carries state and/or exposes multiple operations — an object with data and behavior, a service with methods, a configuration with parameters.

```yaml
"User(login: String)":
  location: User.py
  annotations: |
    Represents a user in the system.
    `login`: the user's login identifier
  properties:
    "id -> int": Unique identifier
    "name -> str": Display name
  methods:
    "greet() -> message:String": |
      Returns the full display name.
    "send_welcome_email() -> void:null": |
      Sends a welcome email to this user.
```

The entity signature describes **how to obtain an instance** — what input data is required to construct the type.

**Methods** define available operations. Each method has a unique name, a signature, and an annotation.

**Properties** define the type's data fields. Each property specifies the data type and has an annotation.

### Routine type

A Routine has no `methods` or `properties`. It represents a single operation — a transformer function, factory, validator, parser, or converter.

```yaml
"calculate_total(a: int, b: int) -> total:int":
  location: calculator.py
  annotations: |
    Calculates the sum of two operands.
    `a`: first operand
    `b`: second operand
```

The routine signature describes **the input and output of the sole operation**. The return value carries a semantic label (e.g., `total:int`) where `total` clarifies the meaning of the returned type. If the Routine returns nothing, omit the output.

### Entity vs Routine

| | Entity | Routine |
|---|---|---|
| Has methods/properties | Yes | No |
| Represents | Object with state and behavior | Single operation (input → output) |
| Use for | Services, configurations, data objects | Transformers, factories, validators, parsers |

### Type mutation

Mutation uses the `::` syntax to indicate that a type specializes or extends a base type.

```yaml
"BaseEntity::ExtendedEntity()":
  location: extended.py
  annotations: |
    Extends BaseEntity with additional methods.
  methods:
    "validate() -> bool:null": |
      Validates the entity data.
```

This denotes:

- Source type: `BaseEntity`
- Target form: `ExtendedEntity`

The DSL does not define the mutation mechanism — it may be realized through inheritance, composition, adapter pattern, interface implementation, decorator pattern, or any other strategy. The specification fixes only the fact that **a type exists that represents a concretization of the base type and its extension**.

The number of types involved in mutation is unbounded:

```yaml
"ObjectOne::ObjectTwo::SomeClass()":
  location: leaf.py
```

Semantically, `SomeClass` must be a mutation of both `ObjectOne` and `ObjectTwo`.

**When to use mutation:**

- You must explicitly indicate that the target type specializes or extends a base type
- The agent needs to understand the type relationship to select the correct implementation strategy

**Do not use mutation** when a type merely uses another type as an argument or return value — that is a standard dependency; Imports with a signature or annotations suffice.

### Type embedding

Embedding includes an imported type in the current contract as-is. The cell consumer needs to know the type is available through this cell (re-export).

```yaml
Imports:
  - Types:
      - ExternalService
    From: shared/services

---

"->ExternalService: {}"
```

Restrictions:

- The type must be available via `Imports`
- Embedding from `Usages` is not recommended

**When to use embedding:**

- An imported type must become part of the current contract as-is
- The cell consumer needs to know the type is available through this cell

**Do not embed** if the type is needed only for internal references — an import suffices.

### location

```yaml
"Type()":
  location: file.ext
```

Specifies the logical file placement relative to the current directory root. Restrictions:

- The file must reside at the same directory level as `CODEMANIFEST`
- The file must include an extension
- The path must not traverse parent directories or descend into subdirectories

### Signature

The signature uses free-form notation close to programming language syntax. It:

- Describes the API shape
- Helps the agent understand the expected model
- Does not require a strict formal grammar

Basic requirements:

- The signature describes the contract's input and output
- Input and output must specify a data type
- The output type is paired with a variable/label that conveys the semantic meaning of the returned value

## Annotations

Annotations are the primary mechanism for controlling code generation. They are not descriptions — they are **directives** specifying expected output, API behavior requirements, which practices to apply, and which constraints to enforce.

**Annotations are the sole mechanism for binding a practice to a contract.** A practice connected via Usages or Imports applies only when an annotation references it. Without an annotation, the practice is connected but not applied.

### Levels

Annotations may appear at three levels:

**Global** (document header):

```yaml
Annotations: |
  Use `conventions` for all types.
  Use `testing` for test patterns.
```

When requirements apply to all types in the cell.

**Type-level**:

```yaml
"User()":
  location: user.py
  annotations: |
    Represents a user in the system.
    Use `pattern` for implementation.
```

When defining responsibility, the signature alone does not convey expected behavior, or describing interaction with other cells.

**Method/Property-level**:

```yaml
  methods:
    "handleRequest(req: Request) -> resp:Response": |
      Process incoming HTTP request.
      `req`: the incoming request object
      Use `pattern` for implementation.
```

When operation-specific details are needed: input/output format, side effects, requirements, algorithms.

Annotations at different levels must not:

- Duplicate each other
- Contain implementation details

### References in annotations

Use backtick references (`` ` ``) to point to named document elements:

- **Signature variables** — so the agent identifies the parameter under discussion
- **Usages/Imports practices** — so the agent knows which practice to apply
- **Import types** — so the agent identifies the data types

Restrictions:

- References must be enclosed in backticks, e.g., `` `param` ``
- Annotations must not reference entities outside the current CODEMANIFEST file context

Example:

```yaml
Imports:
  - Types:
      - ObjectOne AS Object
    Usages:
      - usage_from_imports
    From: path/to/cell

Usages:
  usage_link: |
    Pattern example

Annotations: |
  Use `usage_from_imports` from Imports
  Use `usage_link` in this annotations
  Use `Object` link from imports with alias

---

"Repository()":
  location: repository.py
  annotations: |
    Use `usage_from_imports` from Imports
    Use `Object` link from imports with alias
  methods:
    "findById(userId: Int) -> user:List<String>": |
      Use `usage_from_imports` from Imports
      Use `userId` in this annotations
      Use `user` in this annotations
```

## Footer

The footer is optional and serves attribution purposes only. It does not affect the contract or architecture.

```yaml
Author: FirstName LastName
CreatedAt: 01/01/26
Description: |
  Description of CODEMANIFEST file
```

- `Author` — always `Goga`. Do not invent other names — all CODEMANIFEST files carry `Author: Goga`
- `CreatedAt` — creation date in day/month/year format
- `Description` — brief statement of why this manifest exists

## Design order

When designing a CODEMANIFEST file, follow this order:

1. **Header** — define Imports, Usages, Annotations. This establishes the context in which the contract operates
2. **Body** — declare Entity, Routine. With context already set, types leverage available practices and imports
3. **Footer** — record Author, CreatedAt, Description
