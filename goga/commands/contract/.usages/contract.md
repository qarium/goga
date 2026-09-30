# CLI Command: contract

## Purpose

Compare CODEMANIFEST contract with implementation. For each type in the contract, finds the match in code and builds a comparison structure.

## Syntax

```
goga contract <cell_path>... [--lang <language>]
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `cells` | list[str] | One or more paths to cells for comparison |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--lang` | str | from config | Implementation language. Priority: CLI > config.language |

## Output format

JSON structure, where CODEMANIFEST is the source of truth:

```json
{
  "norm/path/to/cell": {
    "TypeName": {
      "signature": { "codemanifest": "...", "implementation": "..." },
      "properties": { "name": { "codemanifest": "...", "implementation": "..." } },
      "methods": { "name": { "codemanifest": "...", "implementation": "..." } },
      "tools": { "tool-name": { "fact": "value" } }
    },
    "RoutineName": {
      "signature": { "codemanifest": "...", "implementation": "..." }
    }
  }
}
```

The `tools` key appears on a type node exactly when at least one installed
tool package contributed at least one fact for that type through the contract
amendment checkpoint; it is absent otherwise — never an empty object. Each key
inside `tools` is the contributing tool's identity.

## Exit code

- 0 — success
- 1 — error (cell not found, configuration error)

## Examples

```bash
goga contract goga/config goga/ast
goga contract goga/config --lang python
```
