---
name: goga-cell-swift
description: Swift: правила реализации контрактов CODEMANIFEST
---
# Swift: правила реализации контрактов

Языковой скилл для Swift.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Examples

Полный пример CODEMANIFEST для Swift со всеми конструкциями DSL:

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

## Особенности языка

**Facade**: только объявления с модификатором `public` составляют фасад. `internal` (по умолчанию) и `private`
не входят в контракт.

**Naming**: camelCase для функций и свойств, PascalCase для типов.

**Value types**: `struct` — value type, `class` — reference type. Выбор определяется семантикой сущности.

**Optionals**: `T?` — optional. В CODEMANIFEST отражается как `T?`.

**Protocol**: протоколы описывают интерфейсы — маппятся в Entity без properties, только methods.

## Маппинг конструкций

| Swift                            | CODEMANIFEST     | Примечание                        |
|----------------------------------|------------------|-----------------------------------|
| `public class` / `public struct` | Entity           | Init параметры → Entity signature |
| `public func` верхнего уровня    | Routine          |                                   |
| `public var` / `public let`      | Property         | Тип из объявления                 |
| `public func` метод              | Method           |                                   |
| `public protocol`                | Entity           | Только methods, без properties    |
| `init` параметры                 | Entity signature |                                   |

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
