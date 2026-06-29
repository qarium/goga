---
name: goga-cell-kotlin
description: Kotlin rules for implementing CODEMANIFEST contracts
---
# Kotlin: Contract Implementation Rules

Language skill for Kotlin.

Apply this specification within the context of the calling skill. Do not restate the content — use it
for making decisions.

Invoked via the `goga-lang-disp` router.

---

## Examples

Complete CODEMANIFEST example for Kotlin demonstrating all DSL constructs:

```yaml
Imports:
  - Types:
      - UserModel
      - CacheConfig AS Config
    Usages:
      - caching
    From: path/to/cache_cell

Usages:
  conventions: .goga/usages/kotlin_conventions.md
  pattern: |
    Use data classes for models. Prefer immutable collections (List, Map) over mutable ones.
  testing: |
    Use JUnit 5. Each public method must have at least one test case.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `caching` from Imports for cache invalidation patterns.

  Use `val` for all properties. Avoid `var` unless mutation is required by contract.

---

"calculateTotal(a: Int, b: Int) -> total: Int":
  location: calculator.kt
  annotations: |
    Calculate the sum of two integers.

    `a`: first operand
    `b`: second operand

    Use `pattern` for implementation.

"UserRepository(config: Config)":
  location: repository.kt
  annotations: |
    Repository for user data access with caching.

    `config`: repository configuration from `Config` type.

    Use `caching` from Imports for cache strategy.
    Use `conventions` for code style.
  properties:
    "tableName -> String": |
      Database table name for users.
    "cacheSize -> Int": |
      Maximum number of cached entries.
  methods:
    "findById(userId: String) -> user: UserModel?": |
      Find a user by ID.

      `userId`: unique user identifier
      `user`: found user or null

      Use `caching` from Imports for cache lookup.
    "deleteById(userId: String)": |
      Delete user by ID.

      `userId`: unique user identifier

"UserModel::AdminUser(userId: String)":
  location: admin.kt
  annotations: |
    Admin user extending UserModel with elevated permissions.

    `userId`: unique user identifier

    Use `caching` from Imports for permission cache.

->UserModel: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for Kotlin.
```

## Cell

A cell is a package/module:

```
cell/
├── CODEMANIFEST
├── *.kt
```

## Language Features

**Facade**: all `public` classes and top-level functions in the package define the facade.
Private and `internal` declarations are not part of the contract.

**Naming**: camelCase for functions and properties, PascalCase for classes.

**Constructors**: Entity signature describes the primary constructor. Constructor parameters are the input data
for obtaining an instance.

**Nullability**: `T?` — nullable, `T` — non-null. CODEMANIFEST represents these directly via `T?` and `T`.

## Construct Mapping

| Kotlin                          | CODEMANIFEST | Note                                   |
|---------------------------------|--------------|----------------------------------------|
| `class` / `data class` (public) | Entity       | Primary constructor → Entity signature |
| Top-level `fun`                 | Routine      | Public function at file level          |
| `val` / `var` class property    | Property     | Type from declaration                  |
| Class method `fun`              | Method       |                                        |

## Implementation

- Public classes and functions
- Use immutable types when possible

## Signature Rules

Allowed:
```
String, Int, Double, Boolean
List<T>, Map<String, T>
T?
```

Forbidden:
```
Any
vararg
untyped collections
```

---
