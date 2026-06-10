---
name: goga-cell-javascript
description: JavaScript CODEMANIFEST contract implementation rules
---
# JavaScript: Contract Implementation Rules

Language skill for JavaScript.

Apply the specification within the context of the invoking skill. Do not paraphrase the contents — use them
to drive implementation decisions.

Invoked via the `goga-lang-disp` router.

---

## Examples

Complete CODEMANIFEST example for JavaScript covering all DSL constructs:

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

## Language Specifics

**Facade**: `index.js` serves as the single entry point. All contract exports flow through `module.exports` or `export`.
Only symbols exported from `index.js` form the cell facade.

**Naming**: Use camelCase for functions and methods; use PascalCase for classes.

**Types**: JSDoc provides type annotations. Signatures cannot be extracted without JSDoc.

**Constructors**: The entity signature describes a `new ClassName()` invocation or a factory function.

## Construct Mapping

| JavaScript Construct   | CODEMANIFEST     | Notes                                        |
|------------------------|------------------|----------------------------------------------|
| Exported `class`       | Entity           | Class fields → properties, methods → methods |
| Exported `function`    | Routine          | Module-level function                        |
| Class method           | Method           |                                              |
| Class field / getter   | Property         | Type inferred from JSDoc                     |

## Implementation

- All exports must go through `index.js`

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
