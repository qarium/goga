# Kotlin: правила реализации контрактов

Языковой скилл для Kotlin.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Examples

Полный пример CODEMANIFEST для Kotlin со всеми конструкциями DSL:

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

## Особенности языка

**Facade**: все `public` классы и функции верхнего уровня в пакете составляют фасад.
Приватные и internal объявления не входят в контракт.

**Naming**: camelCase для функций и свойств, PascalCase для классов.

**Constructors**: Entity signature описывает primary constructor. Параметры constructor'а — это входные данные
для получения экземпляра.

**Nullability**: `T?` — nullable, `T` — non-null. В CODEMANIFEST отражается через `T?` и `T`.

## Маппинг конструкций

| Kotlin                          | CODEMANIFEST | Примечание                             |
|---------------------------------|--------------|----------------------------------------|
| `class` / `data class` (public) | Entity       | Primary constructor → Entity signature |
| `fun` верхнего уровня           | Routine      | Public функция на уровне файла         |
| `val` / `var` свойство класса   | Property     | Тип из объявления                      |
| `fun` метод класса              | Method       |                                        |

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
