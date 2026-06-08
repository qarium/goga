---
name: goga-cell-javascript
description: JavaScript: правила реализации контрактов CODEMANIFEST
---
# JavaScript: правила реализации контрактов

Языковой скилл для JavaScript.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Examples

Полный пример CODEMANIFEST для JavaScript со всеми конструкциями DSL:

```yaml
Imports:
  - Types:
      - EventEmitter
      - TransportConfig AS Config
    Usages:
      - retry_policy
    From: path/to/events_cell

Usages:
  conventions: .goga/usages/js_conventions.md
  pattern: |
    Use async/await for all asynchronous operations. Avoid callbacks.
  testing: |
    Use Jest. Each exported function and class method must have test coverage.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `retry_policy` from Imports for retry logic on transient failures.

  All async functions must return `Promise<T>`.

---

"parseInput(input: string) -> data: Uint8Array":
  location: parser.js
  annotations: |
    Parse raw input string into structured data.

    `input`: raw string to parse

    Use `pattern` for implementation.

"ApiClient(baseURL: string)":
  location: api.js
  annotations: |
    HTTP client for external API communication.

    `baseURL`: root URL for all API requests

    Use `retry_policy` from Imports for request retries.
    Use `conventions` for code style.
  properties:
    "baseURL -> string": |
      Root URL for API requests.
    "timeout -> number": |
      Request timeout in milliseconds.
  methods:
    "fetchData(endpoint: string) -> response: Promise<Object<string, any>>": |
      Fetch data from the specified endpoint.

      `endpoint`: API endpoint path
      `response`: async response data

      Use `pattern` for implementation.
    "close()": |
      Close client and release resources.

"EventEmitter::SocketEmitter(url: string)":
  location: emitter.js
  annotations: |
    Socket-based emitter extending EventEmitter with real-time capabilities.

    `url`: WebSocket server URL

    Use `retry_policy` from Imports for reconnection logic.

->EventEmitter: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for JavaScript.
```

## Cell

A cell is a module:

```
cell/
├── CODEMANIFEST
├── index.js
```

## Особенности языка

**Facade**: `index.js` — единая точка входа. Все экспорты контракта идут через `module.exports` или `export`.
Только то, что экспортировано из `index.js`, составляет фасад ячейки.

**Naming**: camelCase для функций и методов, PascalCase для классов.

**Types**: JSDoc используется для аннотаций типов. Без JSDoc сигнатуры не могут быть извлечены.

**Constructors**: Entity signature описывает вызов `new ClassName()` или фабричную функцию.

## Маппинг конструкций

| JavaScript             | CODEMANIFEST     | Примечание                                   |
|------------------------|------------------|----------------------------------------------|
| `class` в экспортах    | Entity           | Class fields → properties, methods → methods |
| `function` в экспортах | Routine          | Функция на уровне модуля                     |
| Class method           | Method           |                                              |
| Class field / getter   | Property         | Тип из JSDoc                                 |

## Implementation

- All exports go through `index.js`

## Signature Rules

Use JSDoc for type annotations where needed.

Allowed:
```
string, number, boolean
Array<T>
Object<string, T>
T | null
Promise<T>
```

Forbidden:
```
Function
Object (without generics)
...args
```

---
