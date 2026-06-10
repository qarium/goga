# CLI Command: schema

## Purpose

CLI wrapper for the schema command. Delegates business logic to `goga/schema`. Outputs a JSON tree of project CODEMANIFEST cells.

## Syntax

```
goga schema [cells...] [--max-depth N] [--depends-on PATH]
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `cells` | list[str] | Paths to cells for filtering (optional) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--max-depth` | int | None | Nesting depth limit |
| `--depends-on` | list[str] | None | Filter cells by dependency (repeatable) |

## Exit code

- 0 — success
- 1 — AST parsing errors found

## Examples

```bash
goga schema
goga schema goga/config goga/ast --max-depth 2
goga schema --depends-on goga/ast
```
