# DSL Specification for `CODEMANIFEST`

## Purpose

This DSL defines the **public contract surface** of a package.

It describes:
- which entities must be available from the package facade,
- where each entity must be implemented inside the package,
- what API each entity exposes,
- what semantic and behavioral requirements apply,
- which external types are re-exported through the facade.

The DSL defines **what must exist** and **what it must mean**.
It does not dictate the full internal implementation design.

Signatures may be described in free form, close to the target programming language,
to help AI models navigate the contract more effectively.

---

## High-Level Model

A package may contain `CODEMANIFEST` files at different levels of the directory tree.

- **Package root** `CODEMANIFEST` — defines the top-level facade contract.
- **Subpackage** `CODEMANIFEST` — defines the contract for a subpackage.

Each `CODEMANIFEST` describes the entities and functions implemented at its level.

The package is treated as an isolated unit.
Its external interaction is defined through the contract.

The implementation agent may decompose the package internally, but must preserve:
- declared facade entities,
- declared API,
- declared semantics,
- required implementation file locations.

---

## Top-Level Structure

A typical file may look like this:

```yaml
Imports:
  - Types:
      - Object
    From: "identity"

Usages:
  - pydantic: .specs/pydantic.md
  - structures: .specs/structures.md
  - pattern: |
       Annotation describing how to use the `pattern` alias.

Annotations: |
  Description of this package or subpackage.

---

"->Object": {}

"Loader(path: str, cls_prefix: str = 'Test', method_prefix: str = 'test_')":
  location: loader.py
  annotations: |
    Description of the Loader entity.
  methods:
    "load() -> cls_instances:list[Any]": |
      Returns a list of loaded class instances.

"Object::structures.Data::SomeClass()":
  location: some.py
  annotations: |
    Class with data model representation.
  properties:
    name -> str: |
      String with the name.

"fibonacci(n: int) -> number:int":
  location: tools.py
  annotations: |
    Fibonacci number computation.
```

A single `CODEMANIFEST` may contain:
- an `Imports` section (internal types from other `CODEMANIFEST` files in the same project),
- a `Usages` section (external dependencies, external types, patterns, conventions),
- file-level `Annotations` (optional, describes the module or subpackage as a whole),
- re-export blocks (pass-through types),
- entity blocks (classes with properties and/or methods),
- standalone function blocks (top-level blocks without properties or methods).

---

## Top-Level Sections

### `Imports`
Defines **internal** types used in the contract — imports from other `CODEMANIFEST` files within the same project.

External library types (e.g., `requests.HTTPError`) must **not** appear here. They are described in `Usages`.

Example:

```yaml
Imports:
  - Types:
      - Object
      - Helper
    From: "resq/utils"
  - Types:
      - DocumentRoot AS DocumentRootNode
      - HeaderNode
    From: "goga/codemanifest/nodes"
```

Semantics:
- **`Types` import group**: a list of types from another `CODEMANIFEST` used in signatures but not locally defined.
  - `Types` is a list of type names. Each type name uses the name as defined in the source `CODEMANIFEST`.
  - An optional alias can be specified using `AS`: `TypeName AS AliasName`. The alias is the local name used in this contract instead of the original type name.
  - `From` is the package directory path (relative to the working directory) containing the `CODEMANIFEST` where the types are defined. The `CODEMANIFEST` file name itself is not included — it is implied. Path separator must be `/` (filesystem path), not `.` (Python package notation). For example: `"resq/utils"`, not `"resq.utils"`.
- Imported types are **internal contract dependencies** — they come from other packages within the same project.
- External library types are described in `Usages`, not in `Imports`.
- Importing a type does **not** automatically re-export it. Use the re-export syntax to make it available on the facade.
- Types from the same `From` source should be grouped in a single entry. Each entry has exactly one `From` and one `Types` list.

### `Usages`
A general-purpose section for attaching **any external knowledge** the implementation agent needs. `Usages` is not limited to libraries or types — it is an open mechanism for providing context from outside the package.

A usage entry can describe anything:
- an **external library** (how to install, configure, and use its API, including which types to import),
- an **external type** from a third-party library used in signatures (e.g., `requests.HTTPError`, `pydantic.BaseModel`),
- a **convention or pattern** (how to follow a specific design approach),
- a **reference to external code** in another language (e.g., a spec file explaining how to call a Rust/Go/C++ module from Python),
- a **build or toolchain instruction** (how to compile, link, or package something),
- any **external resource** the implementation agent should be aware of — documentation, specs, APIs, protocols, configurations, etc.

External library types used in method signatures or property types must be described in `Usages`, not in `Imports`. `Imports` is reserved for internal project dependencies only.

Example:

```yaml
Usages:
  pydantic: .specs/pydantic.md
  structures: .specs/structures.md
  pattern: |
    Annotation describing how to use the `pattern` alias.
  requests: |
    External HTTP library. Import `HTTPError` for error handling
    and `Response` for return types in method signatures.
    Install: `pip install requests`.
  rust_bridge: .specs/rust_bridge.md
  grpc_api: .specs/grpc_api.md
```

Semantics:
- Each entry key is the **usage name** — any meaningful identifier (library name, pattern name, convention name, resource name).
- The value is either:
  - a **path** to a spec file with detailed documentation (relative to the `CODEMANIFEST` file location),
  - a **multiline text** annotation describing the usage directly.
- `Usages` provides **context only** — it does not create facade entities or import obligations. It informs the implementation agent about external resources and how to work with them.
- `Usages` is separate from `Imports`. `Imports` declares internal types from other `CODEMANIFEST` files. `Usages` describes anything external the implementation depends on.
- External library types referenced in `Usages` may appear in method signatures, property types, or re-exports. The implementation agent reads `Usages` to understand what external types are available and how to import them.
- There is **no restriction** on what a usage entry can reference. If the implementation agent needs to know something from outside the package, it belongs in `Usages`.

### `Annotations` (file-level)
Optional. Provides structured metadata about the `CODEMANIFEST` file as a whole.

Example:

```yaml
Annotations: |
  Description of this package or subpackage.
  May include design rationale, notes, or caveats.
```

Semantics:
- Placed after `Usages` and before the `---` separator.
- Contains global instructions for the agent — requirements for implementation, constraints, architectural expectations, and hints on using practices from `Usages`.
- Annotations apply to the entire document and shape how the contract should be implemented.
- Persists through YAML parsing unlike `#` comments.

### `---` separator
Optional YAML document separator. Used to visually separate `Imports`, `Usages`, and `Annotations` from entity definitions.

### Re-export blocks
Each top-level re-export block makes an imported type available on the package facade without defining a contract for it.

Syntax:

```yaml
"->Name": {}
```

The `->` prefix marks the entity as a re-export.
The empty `{}` body means no contract obligations — the type is passed through as-is.

Example:

```yaml
Imports:
  - Types:
      - Object
    From: "kotlin"

Usages:
  requests: |
    External HTTP library. Provides `HTTPError` for error handling.
---

"->Object": {}
"->requests.HTTPError": {}
```

Semantics:
- The type must be importable from the package facade.
- No `location`, `properties`, or `methods` are defined.
- The type is not a contract entity — no implementation obligation exists.
- The planning agent must ensure the name is available from the package `__init__.py`.
- Re-exports can reference names from `Imports` (internal) or `Usages` (external). Re-exporting from `Usages` is allowed but not recommended — prefer re-exporting internal types from `Imports`. The source of the re-exported name determines how it is imported in the implementation.
- In the case of `Imports`, re-exports can only embed entities from files at lower levels in the filesystem hierarchy relative to the current `CODEMANIFEST`.

### Entity blocks
Each top-level entity block defines one facade-level class.

The entity name can be:
- a **constructor signature** — the full signature including parameters, types, and default values.

Example:

```yaml
"Loader(path: str, cls_prefix: str = 'Test', method_prefix: str = 'test_')":
  location: loader.py
  annotations: |
    Recursively loads classes from the specified directory and creates instances
    with method names by prefix.
  methods:
    "load() -> cls_instances:list[Any]": |
      Returns a list of loaded class instances.

Example():
  location: example.py
  properties:
    name -> str: |
      String with the name
```

`Loader` or `Example` is the contract entity name. It represents a class with properties and methods.

Constructor parameters in the entity name serve as documentation for the implementation agent. They describe how the class should be instantiated but are not enforced as individual contract obligations — the entity as a whole is the contract unit.

### Standalone function blocks
A top-level entity block without `properties` or `methods` represents a standalone function or functor.

The entity name is the full function signature:

```yaml
"fibonacci(n: int) -> number:int":
  location: tools.py
  annotations: |
    Fibonacci number computation.
```

Whether this is implemented as a function or functor depends on the target language characteristics.

`location` is mandatory. `annotations` is optional.

---

## Mutation Syntax `Type::`

An entity block may use the mutation syntax to indicate that the entity **extends an existing type**. The `::` syntax declares that the new entity builds on top of something that already exists.

### What is a mutation?

A mutation means: *"this entity is based on an existing type, adding or changing behavior"*. The DSL deliberately does **not** prescribe **how** this relationship is implemented — it only declares that it exists. The implementation agent chooses the appropriate mechanism:

- **Inheritance** — `class Child(Parent):`
- **Composition with delegation** — a wrapper that holds the original and delegates calls
- **Interface implementation** — `class Impl(Protocol):`
- **Monkey-patching** — extending an existing object at runtime
- **Mixin or trait** — combining behaviors from multiple sources
- Any other mechanism that achieves the semantic relationship

This is why the term "mutation" is used rather than "inheritance" — the relationship is broader than just class inheritance.

### Reading a mutation chain

Read `::` segments from left to right as layers of extension:

```
Object::pydantic.BaseModel::SomeClass()
```

> SomeClass extends BaseModel (from pydantic), which in turn extends Object (from Imports).

The rightmost name before `(` is always the entity being defined. Everything to its left is what it extends.

### Syntax

```yaml
"Type1::Type2::ClassName()":
  location: file.py
  properties:
  methods:
```

Each `Type::` segment before the class name declares a mutation:
- **`TypeName::`** — mutates an existing type. The type may come from `Imports` (internal) or `Usages` (external).
  - Types from `Imports` use the simple type name (e.g., `Object::`).
  - Types from `Usages` use a qualified name: `usage.Type::` (e.g., `pydantic.BaseModel::`), where `usage` is the key in the `Usages` section and `Type` is the type name within that usage.

The last segment before `(` is always the class name (with optional constructor signature).

Example:

```yaml
Imports:
  - Types:
      - Object
    From: "identity"

Usages:
  pydantic: |
    Data validation library. Import `BaseModel` for base class inheritance.
    Import: `from pydantic import BaseModel`

---

"Object::pydantic.BaseModel::SomeClass()":
  location: some.py
  annotations: |
    Class with data model representation.
  properties:
    name -> str: |
      String with the name.
```

Here:
- `Object::` — mutates the `Object` type from `Imports` (internal type from `identity`), using the simple type name,
- `pydantic.BaseModel::` — mutates the `BaseModel` type from `Usages` (external type from pydantic), using the qualified `usage.Type` syntax,
- `SomeClass()` — the class name with optional constructor signature.

Semantics:
- The syntax `Type::` before the class name means "extends an existing interface" — how the mutation is implemented is up to the implementation agent.
- Multiple `Type::` segments indicate multiple mutations (e.g., multiple inheritance, interface implementation).
- The class name after the last `::` may include a constructor signature: `Type::ClassName(arg: Type)`.
- The type is resolved from `Imports` or `Usages` — no prefix distinction is needed.
- Types from `Imports` use simple names: `TypeName::`. Types from `Usages` use qualified names: `usage.TypeName::`.
- Every type referenced in `Type::` mutations **must** have a corresponding entry in `Imports` (for internal types) or `Usages` (for external types) that explicitly declares that type.

---

## Entity Block Semantics

Each entity block may contain:

- `location` (mandatory)
- `annotations` (optional)
- `properties` (optional)
- `methods` (optional)

### `location`
`location` is mandatory.

Example:

```yaml
location: example.py
```

Semantics:
- defines the required file inside the package where the entity must be implemented,
- the entity must be implemented in that file,
- the entity must also be available from the package facade.

This means `location` defines a **location obligation** and the contract defines a **facade obligation**.

`location` is relative to the `CODEMANIFEST` file that defines the entity.

Restrictions:
- The file must be at the same directory level as the `CODEMANIFEST` file.
- The file must include its extension (e.g., `loader.py`, not `loader`).
- The path must not navigate up (`..`) or descend into subdirectories.

### `annotations`
`annotations` is optional. Provides structured metadata about the entity that persists through YAML parsing.

Example:

```yaml
"Loader(path: str)":
  location: loader.py
  annotations: |
    Description of the entity.
    May include notes about source, design decisions, or caveats.
```

Semantics:
- Contains prescriptive instructions for the implementation agent — what is expected on the output, how the API should behave, which practices to apply, which constraints to follow.
- Annotations define behavioral requirements that the implementation must satisfy.
- Persists through YAML parsing unlike `#` comments.
- May reference practices from `Usages` to guide the implementation approach.
- Planning agents must treat annotation text as requirements that shape the generated code.

### `properties`
Properties describe facade-visible data access of the entity.

Properties use a mapping format — the key contains the property name and type, the value is a description.

Example:

```yaml
properties:
  name -> str: |
    String with the name.
  items -> list[Item]: |
    List of items in the collection.
```

Properties section may be omitted when the entity has no facade-visible properties.

#### Property format

```text
PropertyName -> Type: |
  Description text
```

Semantics:
- `PropertyName` = actual property name in code (left side of the mapping key, before `->`)
- `Type` = the property type (right side of the mapping key, after `->`)
- The value is a multiline text containing a human-readable description

Important:
- the key contains both the real code-facing property name and its type,
- the value contains the human-readable description,
- this format is language-agnostic and easy to read.

#### What counts as a property

The properties section covers any facade-visible data accessor, regardless of implementation mechanism:
- `@property` decorated methods,
- public instance attributes (set in `__init__`, no `_` prefix).

From the facade perspective these are indistinguishable — a consumer cannot tell whether `obj.name` is a `@property` or a plain attribute. The contract treats them the same.

#### Property description
The multiline text under the property is mandatory.
It describes:
- what the property represents,
- constraints,
- behavior expectations where relevant.

### `methods`
Methods describe facade-visible callable API of a class.

Methods use a mapping format — the key is the full method signature, the value is the description.

Example:

```yaml
methods:
  "load() -> cls_instances:list[Any]": |
    Returns a list of loaded class instances with the specified prefix
    created using the pattern `Class(method_name)`, where `method_name`
    is each method in the class matching `method_prefix`.
  "get_address(order: Order) -> delivery:Address": |
    Returns the delivery address for the given order.
```

Methods section may be omitted when the entity has no facade-visible callable API (rare but valid).

#### Method signature format

```text
method(arg: Type) -> label:ReturnType
```

Semantics:
- `method` = actual method name in code
- `arg: Type` = actual API argument and its type
- `label` = semantic hint describing the return meaning
- `ReturnType` = actual return type

The return label is explanatory and may clarify meaning when the return type alone is too generic or ambiguous.

Example:

```text
get_address(order: Order) -> delivery:Address
```

Here:
- `get_address` is the actual method name,
- `order` is the argument,
- `delivery` explains which kind of address is meant,
- `Address` is the actual return type.

#### Method description
The multiline text under the method is mandatory.
It describes:
- purpose,
- behavior,
- constraints,
- expectations,
- implementation-relevant semantics.

It must be reflected in:
- execution planning,
- validation,
- tests.

---

## Hierarchical Contracts

A package may have `CODEMANIFEST` files at multiple levels.

Example:

```
some_package/
├── CODEMANIFEST              ← top-level facade: re-exports, top-level entities
├── http/
│   ├── CODEMANIFEST          ← HTTP entities: HTTPClient, HTTPSession, etc.
│   └── ...
└── utils/
    ├── CODEMANIFEST          ← utility functions: join, add_subdomain_to_url
    └── ...
```

Rules:
- Each `CODEMANIFEST` describes entities and functions at its level only.
- `location` paths are relative to the `CODEMANIFEST` file location.
- A parent `CODEMANIFEST` may re-export entities from child `CODEMANIFEST` files using `->` re-exports.
- A child `CODEMANIFEST` does not need to reference its parent.

---

## Facade Scope

The package facade is the set of names available via `import package` or `from package import ...`.

Facade exposure may happen at different levels:
- **primary facade** — available from the top-level `__init__.py`,
- **secondary facade** — available from a subpackage `__init__.py` (e.g., `package.submodule`).

Every entity defined in `CODEMANIFEST` (including re-exports) must be available from at least one facade level.

The contract does not currently distinguish primary from secondary facade. Both are valid facade exposure. The planning agent must verify that each entity is importable from the declared facade location.

---

## Meaning of the DSL

The DSL defines:
- required facade entities,
- required API shape,
- required implementation locations,
- behavioral meaning from descriptions,
- internal contract dependencies (via `Imports`),
- external dependencies and types (via `Usages`),
- re-exported types,
- standalone functions (as top-level blocks without properties/methods),
- interface mutations via `Type::` syntax.

The DSL does **not** automatically define:
- internal module decomposition,
- helper classes,
- helper functions,
- internal validation layers,
- private abstractions.

Those may be introduced by the implementation agent as internal decisions, as long as the contract is preserved.

---

## Boundary Rules Implied by the DSL

The contract implies the following:

1. The package facade is authoritative.
2. Contract entities must remain available from the facade.
3. Each contract entity must be implemented in its declared `location`.
4. Internal decomposition is allowed.
5. Internal decomposition must not erase or distort the contract.
6. Imported contract types define internal dependencies (from other `CODEMANIFEST` files in the same project). External dependencies are described in `Usages`.
7. Re-exported types must be available from the facade but carry no implementation obligation.
8. Re-exports can only embed entities from lower filesystem levels.
9. Package boundaries are user-defined and must be preserved.
10. Subpackage contracts are independent — each `CODEMANIFEST` owns its level.
11. Entity names may contain constructor signatures to document instantiation expectations.
12. The `Type::` mutation syntax declares interface mutation without prescribing implementation.

---

## Planning Consequences

A planning agent should use this DSL to answer:
- What must be present on the facade?
- What must be implemented in which file?
- What is already implemented?
- What is missing?
- What should be added internally to realize the contract?
- What must be re-exported without implementation?
- What standalone functions must be implemented?
- What interface mutations are required?
- What must be tested to prove contract compliance?

---

## Notes for Multi-Entity Contracts

A single `CODEMANIFEST` may describe multiple entities, functions, and re-exports.

Entities may:
- share a single `location`,
- point to different `location` files,
- depend on imported contract types,
- mutate other types via `Type::` syntax,
- belong to the same facade surface.

This is valid.

There is no global rule that one contract entity must correspond to one implementation file.

The user defines the contract.
The planning and coding agents must preserve it.
