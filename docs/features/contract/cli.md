# goga contract

Compare CODEMANIFEST declarations with source code implementation.

## Synopsis

```bash
goga contract [CELLS]... [--lang LANGUAGE]
```

## Description

`goga contract` extracts contract information from source code files using tree-sitter-based parsers and compares the extracted signatures against the corresponding CODEMANIFEST declarations. For each cell, it produces a JSON report showing side-by-side `codemanifest` vs. `implementation` values for every entity, property, method, and routine.

This command is useful for detecting drift between what is declared in CODEMANIFEST files and what is actually implemented in the codebase.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `CELLS` | no | Zero or more cell paths to compare (variadic). When omitted, no cell is compared and the output is an empty JSON object. |

## Options

| Option | Default | Description |
|---|---|---|
| `--lang` | from config | Implementation language. Overrides the `language` value from `.goga/config.yml`. |

## Supported Languages

| Language | `--lang` value |
|---|---|
| Python | `python` |
| Go | `golang` |
| Kotlin | `kotlin` |
| Swift | `swift` |
| JavaScript | `javascript` |

## Output

The command outputs a JSON object to stdout. Each top-level key is a normalized cell path. Within each cell, entities and routines are compared:

```json
{
    "path/to/cell": {
        "EntityName": {
            "signature": {
                "codemanifest": "(...)",
                "implementation": "(...)"
            },
            "properties": {
                "fieldName": {
                    "codemanifest": "String",
                    "implementation": "str"
                }
            },
            "methods": {
                "methodName": {
                    "codemanifest": "(...) -> String",
                    "implementation": "(...) -> str"
                }
            }
        },
        "RoutineName": {
            "signature": {
                "codemanifest": "() -> void",
                "implementation": "(...)"
            }
        }
    }
}
```

A `null` value in the `implementation` field indicates the entity, property, or method was not found in the source code.

## Examples

Compare a single cell using the language from config:

```bash
goga contract src/core/user
```

Compare multiple cells with an explicit language:

```bash
goga contract src/core/user src/core/auth --lang python
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Comparison completed successfully |
| `1` | Error (cell not found, package not importable, config error, or other failure) |
