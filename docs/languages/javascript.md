# JavaScript Contract Extraction

## Overview

The JavaScript extractor reads `index.js` from a module directory and uses **tree-sitter-javascript** to parse it. It identifies exported classes and functions, extracting their public API surface. Both ESM (`export`) and CommonJS (`module.exports`) patterns are supported.

## API

```python
from goga.contract.javascript import javascript_contract

contracts = javascript_contract("path/to/module")
# Returns list[EntityContract | RoutineContract]
```

`javascript_contract` accepts a path to a JavaScript module directory (containing `index.js`). Returns an empty list if `index.js` is missing.

## What Gets Extracted

| Source Construct | Contract Type | Notes |
|---|---|---|
| `export class X { ... }` | `EntityContract` | Methods and fields collected |
| `export function x() {}` | `RoutineContract` | Named exports |
| `export default function() {}` | `RoutineContract` | Name is `"default"` |
| `export default class { ... }` | `EntityContract` | Name is `"default"` |
| `module.exports = { x() {} }` | `RoutineContract` | CommonJS object exports |
| `export { x }` | Varies | Re-exports resolved to original declaration |

### Visibility Rules

- Only exported symbols are included
- Private class methods (`#method`) are excluded
- Private class fields (`#field`) are excluded
- Non-exported declarations are ignored
- Default exports of non-callable values (e.g. `export default 42`) are skipped

### JSDoc Type Enrichment

When JSDoc comments (`/** ... */`) are present, the extractor enriches signatures with type information from `@param`, `@returns`, and `@type` tags. Parameters without JSDoc annotations appear without types.

## Key Node Types

The parser walks these tree-sitter node types:

- `class_declaration` / `class` -- class declarations and expressions
- `function_declaration` -- function declarations
- `arrow_function` -- arrow function expressions
- `method_definition` -- class methods
- `field_definition` -- class fields (public only)
- `export_statement` -- ESM exports
- `export_clause` / `export_specifier` -- named re-exports

## Example

Given an `index.js`:

```javascript
/**
 * @param {string} name
 * @returns {number}
 */
export function calculate(name) {
  return 42;
}

export class Server {
  constructor(host) {}
  start() {}
}
```

The extracted contracts are:

| Name | Type | Signature |
|---|---|---|
| `Server` | EntityContract | `()` |
| `calculate` | RoutineContract | `(name: string) -> number` |

`Server` has two methods (`constructor(host)`, `start()`). The `calculate` function signature is enriched with JSDoc types.

## CommonJS Support

The extractor handles `module.exports` patterns:

```javascript
module.exports = {
  create(name) {},
  destroy() {},
};
```

This produces two `RoutineContract` items with names `create` and `destroy`.
