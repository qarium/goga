# Kotlin Contract Extraction

## Overview

The Kotlin extractor scans a package directory for `.kt` files and uses **tree-sitter-kotlin** to parse them. It identifies classes, object declarations, top-level functions, and extension functions, extracting only public declarations.

## API

```python
from goga.contract.kotlin import kotlin_contract

contracts = kotlin_contract("path/to/package")
# Returns list[EntityContract | RoutineContract]
```

`kotlin_contract` accepts a path to a Kotlin package directory. Returns an empty list if no `.kt` files are found.

## What Gets Extracted

| Source Construct | Contract Type | Notes |
|---|---|---|
| `class X(val p: T)` | `EntityContract` | Primary constructor params form signature |
| `data class X(...)` | `EntityContract` | Same as regular class |
| `object X { ... }` | `EntityContract` | Signature is always `()` |
| `interface X { ... }` | `EntityContract` | Abstract methods collected |
| `fun x(): T` | `RoutineContract` | Top-level public functions |
| `fun X.ext(): T` | `MethodContract` | Extension functions attached to receiver class |

### Visibility Rules

- Only public declarations are included (Kotlin default is public)
- `internal`, `private` declarations are excluded
- `companion object` members are skipped
- Nullable types (`String?`) are preserved in signatures

## Key Node Types

The parser walks these tree-sitter node types:

- `class_declaration` -- class, data class, sealed class, interface, and annotation class declarations
- `object_declaration` -- singleton object declarations
- `function_declaration` -- top-level and extension functions
- `property_declaration` -- class properties with type annotations

## Example

Given a Kotlin file `UserService.kt`:

```kotlin
class UserService(val name: String) {
    fun greet(): String = "Hello $name"
}

object Config {
    val host: String = "localhost"
    fun load(): Config = this
}

fun formatName(firstName: String, lastName: String): String =
    "$firstName $lastName"
```

The extracted contracts are:

| Name | Type | Signature |
|---|---|---|
| `Config` | EntityContract | `()` |
| `UserService` | EntityContract | `(name: String)` |
| `formatName` | RoutineContract | `(firstName: String, lastName: String) -> String` |

`UserService` has one method (`greet() -> String`). `Config` has one property (`host: String`) and one method (`load() -> Config`).

### Extension Functions

Extension functions are attached to their receiver entity. For example:

```kotlin
class User
fun User.greet(): String = "Hello"
```

The `greet` method appears on the `User` entity rather than as a standalone routine.
